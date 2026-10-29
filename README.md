# 服务器初始拥塞窗口与网站加载性能测量

> 计算机网络技术课程答辩项目 · 三人小组 · 答辩日期 2026-11-08
>
> 仓库：https://github.com/JHTF1/iw-page-load

## 这个项目在做什么

用两套互补的实验回答一个真实的网络工程问题：**服务器的初始拥塞窗口（initcwnd）对网页加载性能到底有多大影响，服务器该不该调它。**

- **真实站点实验**：抓包测出 25 个真实网站服务器的 initcwnd，同时用浏览器测它们的加载性能，做相关性分析。
- **受控实验**：在 WSL2 里自建 nginx，人为把 initcwnd 设成 2、4、10、20 四组，用 `tc netem` 加固定时延，测同一页面的加载时间，得到因果结论。
- **自校准**：受控实验的 initcwnd 是已知真值，先用它验证抓包算法（误差不超过 1 个 MSS），算法可信之后才去测真实网站。

结论严格分级：真实站点数据只说"相关"，受控实验数据才说"因果"。

## 两条铁律

1. **测 initcwnd 只用 curl 单连接。** 浏览器并行连接会干扰首窗口。
2. **测加载性能必须禁用 QUIC。** Chrome 启动加 `--disable-quic`，否则 HTTP/3 站点与 TCP 指标不可比。

## 当前状态

**v0.1.0 骨架阶段。** 目录、公共模块、数据契约、配置、文档、测试和 CI 已就位；`src/capture/`、`src/measure/`、`src/analysis/` 三个模块目前只有接口桩，分别由 A、B、C 在各自分支上实现。

## 目录结构

```
iw-page-load/
├─ README.md
├─ requirements.txt
├─ pyproject.toml
├─ .gitignore
├─ check_env.py                 环境与抓包自检
├─ config/
│  ├─ sites.csv                 站点清单
│  └─ settings.yaml             全局参数
├─ src/
│  ├─ common/                   公共契约：路径、配置、字段、日志、图表规范
│  ├─ capture/                  A：initcwnd 测量
│  ├─ measure/                  B：页面加载性能测量
│  └─ analysis/                 C：合并、统计、绘图
├─ experiment/server/           B：受控实验平台（WSL + nginx + tc netem）
├─ data/raw/                    pcap，不入库
├─ data/processed/              两份 CSV，入库
├─ results/figures/             图表，PNG + SVG
├─ results/tables/              统计结果表
├─ tests/                       单元测试
├─ docs/                        设计、数据字典、协作规范、实验记录、报告框架
└─ .github/workflows/tests.yml  CI
```

## 环境要求

- Windows 10/11 + Python 3.13
- 抓包需要**管理员权限**启动终端或 PyCharm
- 本机抓包后端为 **WinPcap 4.1.3**（为兼容 eNSP 保留，未安装 Npcap）
- 受控实验需要 WSL2，并且在 WSL 内具备 root 权限

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 快速开始

```bash
# 1. 环境与抓包自检（需管理员权限）
python check_env.py

# 2. 单站点抓包并测 initcwnd（A 的模块，待实现）
python -m src.capture --site baidu --url https://www.baidu.com/

# 3. 批量测量页面加载性能（B 的模块，待实现）
python -m src.measure --sites config/sites.csv

# 4. 合并、统计并出图（C 的模块，待实现）
python -m src.analysis

# 5. 跑测试
pytest
```

三个模块的 `--help` 在当前骨架阶段已经可用。

## 数据契约

两份 CSV 是三人之间唯一的数据接口，字段定义在 `src/common/schema.py`，完整说明见 [docs/数据字典.md](docs/数据字典.md)。

- `data/processed/initcwnd.csv`：站点、服务器 IP、initcwnd 字节数与 MSS 倍数、方法、置信度
- `data/processed/pageload.csv`：站点、各阶段耗时、请求数、传输字节、QUIC 与缓存状态

合并键是 `site`；受控实验统一写成 `lab-2`、`lab-4`、`lab-10`、`lab-20`。

**字段变更必须走 PR 并经三人确认，任何人在 feature 分支上不得私自改 schema。**

## 分工

- **A**：TCP 测量端到端。`src/capture/`、受控实验算法校准、真实站点抓包、第 1 与第 3 章、Git 与 CI 维护。
- **B**：应用层测量端到端。`src/measure/`、受控实验平台、真实站点测量、第 2 与第 4 章、站点清单与实验记录模板。
- **C**：数据端到端。`src/analysis/`、数据契约与假数据管线、统计检验与图表、第 5 与第 6 章、统稿与 PPT。

三人的代码量、实验量、写作量基本对齐，详见 [docs/项目总体设计.md](docs/项目总体设计.md) 第 7 节。

## Git 协作

采用 GitHub Flow：`main` 受保护，三人各一条 `feature/` 分支，PR + Merge commit 合并，里程碑打 tag。

- `v0.1.0` 骨架（当前）
- `v0.5.0` 数据采集完成
- `v1.0.0` 答辩冻结版

提交信息格式 `type(scope): 描述`，例如 `feat(capture): 实现首窗口字节统计`。详细规范见 [docs/分工与协作规范.md](docs/分工与协作规范.md)。

## 注意事项

- **抓包必须管理员权限**；`check_env.py` 会打印可用网卡并做 5 秒抓包自检。
- **只测公开可访问的网站首页**，不做端口扫描、不做压力测试。
- **pcap 严禁提交**（`.gitignore` 已忽略 `data/raw/*`），只提交处理后的 CSV。
- **真实实验必须冷缓存、禁用 QUIC**，数据里 `quic_disabled` 必须为 `true`，`cache_mode` 必须为 `cold`。
- 每次实验都要在 [docs/实验记录.md](docs/实验记录.md) 里登记环境、时段、网络和异常剔除情况。
- 图表统一走 `src/common/style.py`，图题在图下方，PNG 与 SVG 双份。

## 文档

- [docs/项目总体设计.md](docs/项目总体设计.md)：技术路线、数据契约、分工、时间计划、评分表映射、风险对策
- [docs/数据字典.md](docs/数据字典.md)：两份 CSV 的字段说明与校验规则
- [docs/分工与协作规范.md](docs/分工与协作规范.md)：分支、提交、PR、评审、推送流程
- [docs/实验记录.md](docs/实验记录.md)：实验记录模板与控制变量
- [docs/报告框架.md](docs/报告框架.md)：六章结构、图表位置、国标检查清单

## 参考

- RFC 6928: Increasing TCP's Initial Window
- RFC 5681: TCP Congestion Control
- GB/T 7713.1-2006 学位论文编写规则
- GB/T 7714-2015 信息与文献 参考文献著录规则
- GB 3100~3102 量和单位
