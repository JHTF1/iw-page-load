"""Chrome DevTools 协议客户端。

TODO(B):
1. 以 --remote-debugging-port 启动本机 Chrome，必须附加 --disable-quic
2. 通过 websocket 建立会话，启用 Page / Network / Runtime 域
3. 导航到目标 URL，等 load 事件后取 Navigation Timing 与资源条目
"""

from __future__ import annotations


class ChromeSession:
    def __init__(self, binary: str | None = None, port: int = 9222) -> None:
        self.binary = binary
        self.port = port

    def __enter__(self) -> "ChromeSession":
        raise NotImplementedError("TODO(B): 启动 Chrome 并建立 CDP 会话")

    def __exit__(self, *exc_info: object) -> None:
        return None

    def navigate(self, url: str, timeout_ms: int = 30000) -> dict:
        """打开页面并返回 Navigation Timing 与资源统计。

        TODO(B)。
        """
        raise NotImplementedError(f"TODO(B): 导航到 {url}")
