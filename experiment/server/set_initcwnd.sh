#!/usr/bin/env bash
# 修改出口网卡上所有路由的初始拥塞窗口（单位：报文段）。
# 用法：set_initcwnd.sh <正整数>，受控实验取 2 / 4 / 10 / 20。
#
# 注意：WSL2 里客户端（Windows 宿主）与服务器同在一个虚拟子网，回程流量走的是
# on-link 子网路由而不是默认路由，因此必须同时改默认路由和网段路由，否则设置不生效。
set -euo pipefail

log() { printf '[initcwnd] %s\n' "$*"; }
die() { printf '[initcwnd] 错误: %s\n' "$*" >&2; exit 1; }

N="${1:-}"
case "$N" in
  ""|*[!0-9]*) die "用法: $0 <正整数>，例如 $0 10" ;;
esac
[ "$N" -ge 1 ] || die "initcwnd 必须大于等于 1，当前 $N"

command -v ip >/dev/null || die "缺少 iproute2（找不到 ip 命令）"

if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
else
  SUDO=""
fi

ROUTE="$(ip route show default | head -n 1)"
[ -n "$ROUTE" ] || die "找不到默认路由（WSL2 未启动或网络异常）"

DEV="$(printf '%s\n' "$ROUTE" | awk '{for (i = 1; i < NF; i++) if ($i == "dev") print $(i + 1)}')"
GW="$(printf '%s\n' "$ROUTE" | awk '{for (i = 1; i < NF; i++) if ($i == "via") print $(i + 1)}')"
[ -n "$DEV" ] || die "无法从默认路由解析网卡：$ROUTE"

count=0
# 默认路由
if [ -n "$GW" ]; then
  log "修改默认路由：via $GW dev $DEV initcwnd=$N"
  $SUDO ip route change default via "$GW" dev "$DEV" initcwnd "$N"
else
  log "修改默认路由：dev $DEV initcwnd=$N"
  $SUDO ip route change default dev "$DEV" initcwnd "$N"
fi
count=$((count + 1))

# 同一网卡上的其它路由（含回程实际使用的 on-link 网段路由）
while read -r line; do
  dest="$(printf '%s\n' "$line" | awk '{print $1}')"
  [ "$dest" = "default" ] && continue
  case "$dest" in
    ""|"unreachable"|"blackhole"|"prohibit"|"throw") continue ;;
  esac
  log "修改网段路由：$dest dev $DEV initcwnd=$N"
  $SUDO ip route change "$dest" dev "$DEV" initcwnd "$N"
  count=$((count + 1))
done < <(ip route show dev "$DEV")

log "已修改 $count 条路由，当前路由表："
ip route show
log "注意：内核不回显 initcwnd 之外的证据，命令回显不能作为充分证据，建议用 ss -ti 或抓包确认实测初窗。"
