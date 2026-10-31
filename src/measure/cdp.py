"""Chrome DevTools 协议客户端。

每次会话启动一个使用独立临时 profile 的 Chrome，通过 CDP 控制导航并读取
Navigation Timing，从而保证每轮测量都是冷缓存、且不携带历史站点数据。

铁律：启动参数必须带 ``--disable-quic``；导航结果里若出现 ``h3``，由上层
（metrics.build_record）判为 QUIC 未禁用并拒绝写入。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from ..common.logging_setup import get_logger

logger = get_logger("measure.cdp")

# 关闭扩展、后台联网与首次运行引导，避免测量被无关流量干扰
_CHROME_FLAGS = (
    "--disable-quic",
    "--disable-extensions",
    "--disable-component-extensions-with-background-pages",
    "--disable-background-networking",
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1200,800",
)

_REGISTRY_PATHS = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
)

# 跨域资源可能因缺少 Timing-Allow-Origin 而返回 transferSize=0，数据中会偏低
_TIMING_JS = """(() => {
  const n = performance.getEntriesByType('navigation')[0];
  if (!n) { return JSON.stringify({ error: 'no navigation entry' }); }
  const res = performance.getEntriesByType('resource');
  const transfer = res.reduce((s, x) => s + (x.transferSize || 0), 0) + (n.transferSize || 0);
  return JSON.stringify({
    dns_ms: n.domainLookupEnd - n.domainLookupStart,
    tcp_ms: n.connectEnd - n.connectStart,
    tls_ms: n.secureConnectionStart > 0 ? n.connectEnd - n.secureConnectionStart : 0,
    ttfb_ms: n.responseStart - n.requestStart,
    dom_content_loaded_ms: n.domContentLoadedEventEnd,
    load_ms: n.loadEventEnd,
    request_count: res.length + 1,
    transfer_bytes: transfer,
    protocol: n.nextHopProtocol,
    status: n.responseStatus,
    final_url: location.href
  });
})()"""


class ChromeError(RuntimeError):
    """Chrome 启动、CDP 协议或导航失败。"""


def find_chrome(binary: str | None = None) -> str:
    """定位 Chrome 可执行文件。

    ``binary`` 为空或 ``auto`` 时按常见安装路径与注册表查找。
    """
    if binary and binary != "auto":
        path = Path(binary)
        if path.is_file():
            return str(path)
        raise FileNotFoundError(f"指定的 Chrome 不存在: {binary}")

    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(program_files) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(program_files_x86) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    if local_appdata:
        candidates.append(Path(local_appdata) / "Google" / "Chrome" / "Application" / "chrome.exe")

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    if os.name == "nt":
        import winreg

        for key_path in _REGISTRY_PATHS:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    value, _ = winreg.QueryValueEx(key, "")
            except OSError:
                continue
            if value and Path(value).is_file():
                return value

    raise FileNotFoundError(
        "未找到 Chrome，请在 config/settings.yaml 的 measure.chrome_binary 里写绝对路径"
    )


def _http_json(port: int, path: str, timeout: float) -> dict[str, Any] | None:
    """访问 CDP 的 HTTP 端点，绕过系统代理（localhost 不应该走代理）。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}{path}", timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


class ChromeSession:
    """一次 Chrome 会话：启动浏览器、导航、读取性能指标。

    用法::

        with ChromeSession() as session:
            timing = session.navigate("https://www.baidu.com/")
    """

    def __init__(self, binary: str | None = None, port: int = 9222) -> None:
        self.binary = find_chrome(binary)
        self.port = port
        self._proc: subprocess.Popen | None = None
        self._profile: Path | None = None
        self._ws = None
        self._counter = 0

    # ---- 生命周期 ----

    def __enter__(self) -> "ChromeSession":
        # 上一轮 Chrome 可能还在退出，先等端口释放，避免把新会话连到旧实例上
        if not self._wait_port_free(timeout_s=10):
            raise ChromeError(f"调试端口 {self.port} 已被占用，请关闭其他 Chrome 实例")

        self._profile = Path(tempfile.mkdtemp(prefix="iw-page-load-chrome-"))
        args = [
            f"--remote-debugging-port={self.port}",
            *_CHROME_FLAGS,
            f"--user-data-dir={self._profile}",
            "about:blank",
        ]
        logger.info("启动 Chrome: %s", self.binary)
        self._proc = subprocess.Popen(  # noqa: S603
            [self.binary, *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            version = self._wait_until_ready(timeout_s=20)
            logger.info("CDP 就绪: %s", version.get("Browser"))

            target = self._page_target()
            self._ws = connect(target["webSocketDebuggerUrl"], open_timeout=10, close_timeout=5, max_size=None)
            self._request("Page.enable")
            self._request("Network.enable")
            self._request("Runtime.enable")
        except Exception:
            # 建立会话失败时立即回收进程与临时 profile，避免占住端口影响下一轮
            self.__exit__()
            raise
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:  # noqa: BLE001 - 关闭阶段的异常不影响结果
                pass
            self._ws = None
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
        self._proc = None
        # 等调试端口真正关闭，下一轮才能干净地启动新实例
        self._wait_port_free(timeout_s=10)
        if self._profile is not None:
            shutil.rmtree(self._profile, ignore_errors=True)
            self._profile = None
        return None

    # ---- 导航与取数 ----

    def navigate(self, url: str, timeout_ms: int = 30000) -> dict[str, Any]:
        """打开页面，等 ``load`` 事件后返回原始指标。

        返回字典的值为浏览器原始值（未取整、未校验）；导航失败时返回
        ``{"error": "..."}``，由调用方决定是否记录该轮。
        """
        started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._request("Network.clearBrowserCache")
        self._request("Network.setCacheDisabled", {"cacheDisabled": True})

        request_id = self._next_id()
        self._ws.send(
            json.dumps(
                {
                    "id": request_id,
                    "method": "Page.navigate",
                    "params": {"url": url},
                }
            )
        )

        nav_result: dict[str, Any] | None = None
        loaded = False
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ChromeError(f"导航超时（{timeout_ms} ms）: {url}")
            try:
                message = json.loads(self._ws.recv(timeout=remaining))
            except TimeoutError as exc:
                raise ChromeError(f"导航超时（{timeout_ms} ms）: {url}") from exc
            except ConnectionClosed as exc:
                raise ChromeError(f"CDP 连接中断（Chrome 可能已退出）: {url}") from exc

            if message.get("id") == request_id:
                if "error" in message:
                    raise ChromeError(f"Page.navigate 失败: {message['error']}")
                nav_result = message.get("result", {})
            elif message.get("method") == "Page.loadEventFired":
                loaded = True

            if nav_result is not None and loaded:
                break

        error_text = nav_result.get("errorText") if nav_result else None
        if error_text:
            return {"error": error_text}

        timing = self._evaluate(_TIMING_JS)
        if timing.get("error"):
            raise ChromeError(f"读取 Navigation Timing 失败: {timing['error']}")
        timing["timestamp_utc"] = started_at
        return timing

    # ---- 内部工具 ----

    def _wait_until_ready(self, timeout_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._proc is not None and self._proc.poll() is not None:
                raise ChromeError(f"Chrome 启动失败，退出码 {self._proc.returncode}")
            version = _http_json(self.port, "/json/version", timeout=1)
            if version:
                return version
            time.sleep(0.3)
        raise ChromeError(f"Chrome 调试端口 {self.port} 在 {timeout_s}s 内未就绪")

    def _wait_port_free(self, timeout_s: float) -> bool:
        """等待调试端口不再响应，返回是否在超时前释放。"""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if _http_json(self.port, "/json/version", timeout=0.5) is None:
                return True
            time.sleep(0.2)
        return False

    def _page_target(self) -> dict[str, Any]:
        for _ in range(20):
            targets = _http_json(self.port, "/json/list", timeout=2) or []
            pages = [
                target
                for target in targets
                if target.get("type") == "page" and target.get("webSocketDebuggerUrl")
            ]
            if pages:
                return pages[0]
            time.sleep(0.3)
        raise ChromeError("没有找到可用的 page target（Chrome 可能未打开标签页）")

    def _next_id(self) -> int:
        self._counter += 1
        return self._counter

    def _request(self, method: str, params: dict[str, Any] | None = None, timeout: float = 30) -> dict[str, Any]:
        request_id = self._next_id()
        self._ws.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ChromeError(f"CDP 命令超时: {method}")
            try:
                message = json.loads(self._ws.recv(timeout=remaining))
            except TimeoutError as exc:
                raise ChromeError(f"CDP 命令超时: {method}") from exc
            except ConnectionClosed as exc:
                raise ChromeError(f"CDP 连接中断（Chrome 可能已退出）: {method}") from exc
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise ChromeError(f"CDP 命令失败 {method}: {message['error']}")
            return message.get("result", {})

    def _evaluate(self, expression: str) -> dict[str, Any]:
        result = self._request(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
        )
        value = result.get("result", {}).get("value")
        if value is None:
            detail = result.get("exceptionDetails")
            raise ChromeError(f"页面脚本执行失败: {detail}")
        return json.loads(value)
