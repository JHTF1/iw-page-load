#!/usr/bin/env bash
# 设置或清除默认路由网卡上的 netem 时延。
# 用法：set_netem.sh <毫秒数>   例如 set_netem.sh 60
#       set_netem.sh clear     清除规则（实验结束必须执行）
set -euo pipefail

log() { printf '[netem] %s\n' "$*"; }
die() { printf '[netem] 错误: %s\n' "$*" >&2; exit 1; }

MODE="${1:-}"
[ -n "$MODE" ] || die "用法: $0 <毫秒数> 或 $0 clear"
if [ "$MODE" != "clear" ]; then
  case "$MODE" in
    *[!0-9]*) die "毫秒数必须为整数，当前 '$MODE'" ;;
  esac
fi

command -v tc >/dev/null || die "缺少 iproute2（找不到 tc 命令）"

if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
else
  SUDO=""
fi

ROUTE="$(ip route show default | head -n 1)"
[ -n "$ROUTE" ] || die "找不到默认路由（WSL2 未启动或网络异常）"
DEV="$(printf '%s\n' "$ROUTE" | awk '{for (i = 1; i < NF; i++) if ($i == "dev") print $(i + 1)}')"
[ -n "$DEV" ] || die "无法从默认路由解析网卡：$ROUTE"

# 幂等：先清掉旧规则，忽略"不存在"的报错
$SUDO tc qdisc del dev "$DEV" root 2>/dev/null || true

if [ "$MODE" = "clear" ]; then
  log "已清除 $DEV 上的 netem 规则"
else
  $SUDO modprobe sch_netem 2>/dev/null || true
  $SUDO tc qdisc add dev "$DEV" root netem delay "${MODE}ms"
  log "已设置 $DEV 出口净时延 ${MODE}ms"
fi

log "当前 qdisc："
tc qdisc show dev "$DEV"
if [ "$MODE" != "clear" ]; then
  log "请在 Windows 侧 ping WSL IP 验证 RTT 约为 ${MODE}ms（netem delay 为单程）"
fi
