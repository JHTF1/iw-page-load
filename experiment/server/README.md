# 受控实验平台（B 负责）

本目录存放 WSL2 上的受控实验环境脚本。平台的作用：把 initcwnd 变成可控变量，并构造可复现的网络条件。

## 目标

- 在 WSL2 内运行 nginx，提供由 20 个 60 KB 对象组成的测试页面
- 用 `tc netem` 给出口加固定时延（默认 60 ms），让窗口大小成为瓶颈
- 用 `ip route change ... initcwnd N` 切换四组窗口：2、4、10、20
- 每组实验同时抓包，供抓包模块验证"设定值等于实测值"

## 脚本

- `setup_wsl.sh`：安装 nginx 与依赖，生成测试页面，启动服务
- `set_initcwnd.sh N`：对出口网卡上所有路由设置 `initcwnd` 并回显当前值
- `set_netem.sh 60` / `set_netem.sh clear`：设置或清除 `tc netem` 延迟
- `gen_page.py`：生成测试页面与资源文件

脚本可重复执行、幂等、每步有回显、失败时退出码非零。

## 复现步骤

**0. 保持虚拟机常驻。** WSL2 空闲约 8 秒会自动关机，先挂一个常驻会话，否则后续请求会被直接拒绝：

```powershell
wsl -d lab-ubuntu -u root -e sleep infinity
```

**1. 启动平台。**

```bash
wsl -d lab-ubuntu -u root bash experiment/server/setup_wsl.sh
```

**2. 确认 Windows 侧可达**，并记下当次 IP（重启后会变）：

```powershell
wsl -d lab-ubuntu -u root hostname -I
curl http://<wsl-ip>:8080/
```

**3. 加固定时延**，用 ping 确认 RTT ≈ 2 × 设定值：

```bash
wsl -d lab-ubuntu -u root bash experiment/server/set_netem.sh 60
```

**4. 逐组切换窗口**，每组先设定、再确认，最后才采集：

```bash
wsl -d lab-ubuntu -u root bash experiment/server/set_initcwnd.sh 2   # 4 / 10 / 20
```

**5. 采集 5 轮。** 受控组不在 `config/sites.csv` 中，用采集函数直接指定 URL，`site` 固定为 `lab-N`：

```powershell
.\.venv\Scripts\python.exe -c "from src.measure.metrics import collect_site; rows = collect_site('lab-2', 'http://<wsl-ip>:8080/', repeats=5, network_env='wsl-netem-60ms'); rows"
```

`site` 名必须与当前设定的 initcwnd 一致：`lab-2` 只能在 `set_initcwnd.sh 2` 之后采集，否则数据与站点名错配。

**6. 登记**平台信息（WSL 版本、内核版本、netem 参数、设定值与实测值）到 `docs/实验记录.md`。

**7. 复原环境**：清除 netem，把 initcwnd 恢复为 10，关闭虚拟机；不清除 netem 会污染后续真实站点测量。

```bash
wsl -d lab-ubuntu -u root bash experiment/server/set_netem.sh clear
wsl -d lab-ubuntu -u root bash experiment/server/set_initcwnd.sh 10
```

## 口径说明

- 受控组不写入 `sites.csv`：该文件只描述 25 个真实站点，`merge.py` 按 `lab-` 前缀识别受控组，混入配置会污染站点级统计
- 有效 MSS 取客户端 SYN 与服务器 SYN-ACK 的较小值。平台网卡 MTU 为 1432，两端取小后为 1392，四档折算为 2.0 / 4.0 / 10.0 / 20.0；沿用 1460 会把 `lab-10` 算成 9.53
- 测试页为 1 个索引页 + 20 个精确 61440 byte 的合法 PNG，整页 21 个请求、1 235 397 byte

## 注意事项

- WSL2 默认 NAT，Windows 访问需用 WSL 的 IP，或在 Windows 侧配置端口转发
- `tc` 与 `ip route` 需要 root，脚本内自行判断权限
- 修改 initcwnd 后必须立刻抓包验证，不能只相信命令回显
- 实验结束要清除 netem 规则，避免影响后续真实站点测量
