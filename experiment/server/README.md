# 受控实验平台（B 负责）

本目录存放 WSL2 上的受控实验环境脚本。平台的作用：把 initcwnd 变成可控变量，并构造可复现的网络条件。

## 目标

- 在 WSL2 内运行 nginx，提供由 20 个 60 KB 对象组成的测试页面
- 用 `tc netem` 给出口加固定时延（默认 60 ms），让窗口大小成为瓶颈
- 用 `ip route change ... initcwnd N` 切换四组窗口：2、4、10、20
- 每组实验同时抓包，供 A 验证"设定值等于实测值"

## 待创建的脚本

- `setup_wsl.sh`：安装 nginx 与依赖，生成测试页面，启动服务
- `set_initcwnd.sh`：接收一个整数参数，修改路由的 initcwnd 并打印当前值
- `set_netem.sh`：设置或清除 `tc netem` 延迟
- `gen_page.py`：生成测试页面与资源文件

脚本要求：可重复执行、幂等、每步有回显、失败时退出码非零。

## 操作步骤（待 B 落实）

1. 在 WSL 内启动 nginx，确认 Windows 侧能访问 `http://<wsl-ip>:8080/`
2. 执行 `set_netem.sh 60`，用 `ping` 验证 RTT 符合预期
3. 依次执行 `set_initcwnd.sh 2`、`4`、`10`、`20`，每次用 A 的抓包脚本确认实测值与设定值一致
4. 每组用 B 的测量脚本跑 5 轮，`site` 记为 `lab-2`、`lab-4`、`lab-10`、`lab-20`
5. 平台信息（WSL 版本、内核版本、延迟参数）登记到 `docs/实验记录.md`

## 注意事项

- WSL2 默认 NAT，Windows 访问需用 WSL 的 IP，或在 Windows 侧配置端口转发
- `tc` 与 `ip route` 需要 root，脚本内自行判断权限
- 修改 initcwnd 后必须立刻抓包验证，不能只相信命令回显
- 实验结束要清除 netem 规则，避免影响后续真实站点测量
