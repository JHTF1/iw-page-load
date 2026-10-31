#!/usr/bin/env bash
# 受控实验平台初始化：安装 nginx、生成测试页、启动 8080 服务。
# 可重复执行；任一步失败即以非零码退出。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="/var/www/lab"
PORT=8080
SITE_CONF="/etc/nginx/sites-available/iw-lab.conf"
SITE_LINK="/etc/nginx/sites-enabled/iw-lab.conf"

log() { printf '[setup] %s\n' "$*"; }
die() { printf '[setup] 错误: %s\n' "$*" >&2; exit 1; }

if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
else
  SUDO=""
fi

log "1/5 检查依赖"
command -v apt-get >/dev/null || die "仅支持 Debian/Ubuntu（找不到 apt-get）"
command -v python3 >/dev/null || die "缺少 python3"

if ! command -v nginx >/dev/null; then
  log "安装 nginx、iproute2、python3-yaml"
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq nginx iproute2 python3-yaml
fi

log "2/5 生成测试页面到 $WEB_ROOT"
$SUDO python3 "$SCRIPT_DIR/gen_page.py" --out "$WEB_ROOT"

log "3/5 写入 nginx 站点配置 $SITE_CONF"
$SUDO tee "$SITE_CONF" >/dev/null <<EOF
server {
    listen $PORT;
    server_name _;
    root $WEB_ROOT;
    access_log off;
    add_header Cache-Control "no-store";
    location / {
        try_files \$uri \$uri/ =404;
    }
}
EOF
$SUDO ln -sf "$SITE_CONF" "$SITE_LINK"

log "4/5 校验并（重）加载 nginx"
$SUDO nginx -t
if command -v systemctl >/dev/null && $SUDO systemctl is-active --quiet nginx; then
  $SUDO systemctl reload nginx
elif command -v pgrep >/dev/null && pgrep -x nginx >/dev/null; then
  $SUDO nginx -s reload
else
  $SUDO nginx
fi

log "5/5 本机自检 GET http://127.0.0.1:$PORT/"
python3 - "$PORT" <<'PY'
import sys
import urllib.request

url = f"http://127.0.0.1:{sys.argv[1]}/"
with urllib.request.urlopen(url, timeout=5) as resp:
    assert resp.status == 200, f"HTTP {resp.status}"
    body = resp.read()
print(f"[setup] 自检通过：{url} -> 200（{len(body)} 字节）")
PY

WSL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
log "完成。Windows 侧访问：http://${WSL_IP:-<wsl-ip>}:$PORT/"
log "若 Windows 访问不通，在 PowerShell（管理员）执行端口转发："
log "  netsh interface portproxy add v4tov4 listenport=$PORT listenaddress=0.0.0.0 connectport=$PORT connectaddress=$WSL_IP"
