# 局部感知的交错编队形成与车道减少变换

当前工作目录是 `D:\yanjiu1\keyan1`。现行S规则已经安装：真实前车固定时距跟驰、全体车辆局部跨道互选、实际邻道车辆证明的单格补位，以及跟驰与相位冲突时的CTH优先。控制器461行，原版511行；旧提前开隙与等待链已删除，三个私有记忆字段保持。

纯NOA与编队使用相同车辆、发车、速度和物理安全。巡航28.8m/s，最高33.3m/s；巡航同道30m、相邻道交错15m。每车只读取前200m、后100m内各车道实车及自身记忆。

全新61–65种子、八档流量的160例确认全部安全排空。2250、2500辆/h/车道下，600秒需求的平均系统时间分别改善 **15.81%、14.34%**，均5/5种子改善；1800秒八例确认分别改善 **20.08%、17.24%**。燃油相对NOA增加。[本轮完整报告](docs/experiments/2026-11-03-staggered-bottleneck/README.md)列出全部数据、路内行程、入口等待、实际队形和失败版本。

选择组另设保留普通超车及相同合流执行的无编队对照，S仍改善4.49%、8.00%；严格关闭所采用phase子系统后，S再改善2.20%、3.05%，均5/5。几何与[匹配归因](docs/experiments/2026-11-03-staggered-bottleneck/matched_nonformation31_and_S170/tables.md)共同支持形成/变换机制的作用。

## 接续研究

1. [现行系统说明](docs/原生SUMO编队变换系统说明.md)：逐条规则、每个方法、代码结构、执行顺序和指标。
2. [本轮报告与数据入口](docs/experiments/2026-11-03-staggered-bottleneck/README.md)：拥堵诊断、分别尝试的文献机制、失败版本、配对数据及采用证据。
3. [检查点末尾](docs/phase5_checkpoint.md)：当前已安装版本、最新运行及剩余事项。
4. [真实形成与变换图](docs/experiments/2026-11-03-staggered-bottleneck/formation_demo_S_long/README.md)：原24辆随机初态和45辆预成形的实际轨迹。
5. [文献目录](docs/research/2026-10-30-literature-review/README.md)、[MATLAB活跃调用链](docs/2026-10-29-MATLAB车辆控制调用链核查.md)、[本轮方法依据](docs/experiments/2026-11-03-staggered-bottleneck/methods/reference_design.md)。

## 打开实时窗口

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
python -B runrun.py --check
python -B runrun.py
```

也可直接在VS Code中运行本文件夹的 `runrun.py`。窗口和第一次计算同步，每算0.1秒推进一帧。默认每道1250辆/h、600秒、seed1；配置位于脚本顶部。需要观察持续瓶颈时，将 `FLOW_VEH_H_LANE` 改为2250或2500。`--gui-delay-ms 0`加快显示，`--no-wait`结束后自动关闭。

原路为0–1000m三道、1000–1200m两道，准备区从640m开始。查看同道距离时采用 `D(v)=5.5+0.8506944444v`；巡航时看30m/15m交错，合流后看真实两道恢复。45辆两道巡航队形跨度约660m，整队几何另用2400m道路观察，交通效率仍在原1200m道路比较。

无窗口短测：

```powershell
python -B runrun.py --headless --duration 20 --max-time 120 --no-wait
python -B variants/phase5g_pure_formation/run_native_flow.py --mode noa --flow 2250 --duration 600 --max-time 1200
python -B variants/phase5g_pure_formation/run_native_flow.py --mode transform --flow 2250 --duration 600 --max-time 1200
```

## 方法与代码

实际前车跟驰决定本车的时距目标和速度。全体车辆从真实相邻道互选关系取得交错相位；已有前车的车辆保留实际前车参考，相位与CTH要求相反调速时优先CTH。没有近前车时，只有相邻道实车直接证明一格空位，才衔接60m内真实前车。

自由补位同时检查局部车道负荷、真实交错空位、物理走廊及本车和前后车的公开跟驰响应成本。横移跟踪目标道实际前后车空隙；必要合流优先，SUMO逐步执行，安全上限始终保留。

| 文件 | 职责 |
| --- | --- |
| [runrun.py](runrun.py) | 用户配置、实时窗口和自检 |
| [native_rules.py](variants/phase5g_pure_formation/noa/native_rules.py) | 全部纯规则控制与三个私有记忆字段 |
| [native_sumo.py](variants/phase5g_pure_formation/experiments/native_sumo.py) | 路网、伯努利来车、局部观测、真实执行和记录 |
| [run_native_flow.py](variants/phase5g_pure_formation/run_native_flow.py) | 单次实验和固定矩阵入口 |
| [native_comparison.py](variants/phase5g_pure_formation/experiments/native_comparison.py) | 需求/源码核验、逐车重算和配对 |
| [本轮实验工具](docs/experiments/2026-11-03-staggered-bottleneck/tools/README.md) | 冻结、紧凑封存与独立复算 |

`formation_state=1`表示本车已有编队跟驰、被跟驰或实际跨道互选关系；允许仍在调距。纯NOA为0。参与率、同时参与人数、连续1时长直接统计这些本车输出；同时人数可包含多支队伍。几何采用实际位置与速度另行展示。

## 验证与版本

已安装源码SHA256：`8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`。实际磁盘233项测试和43项子测试、9项GUI入口测试、依赖自检均通过；根入口真实短测22/22辆安全排空。[安装验收](docs/experiments/2026-11-03-staggered-bottleneck/implementation/installed_S_verification.json)与[完整规则测试](variants/phase5g_pure_formation/tests/test_local_staggered_rules.py)保留对应证据。

版本保存在[GitHub仓库](https://github.com/32780542/yanjiu1)。远端 `yanjiu1` 对应该仓库，`origin`是历史仓库。各候选保存补丁和源SHA；数据按完整计划分组封包，单包小于20MB，逐件核验后清理本轮可替代大轨迹，不复制整份项目存版本。选定几何案例保留完整轨迹；未封口失败原件及状态继续保存。

历史[TM报告](docs/experiments/2026-10-30-rule-trials/研究结果与采用说明.md)、[P验收](docs/2026-10-29-P独立验收报告.md)及[Cai原文对照](docs/Cai2024全局方案对照依据.md)保留原版本含义。历史自建global入口继续存档，现行结论来自同输入的实际NOA、编队和匹配对照。

本轮已清理约1.05GB可替代轨迹；失败原件及关键完整轨迹保留。详见[存储复核](docs/experiments/2026-11-03-staggered-bottleneck/storage_cleanup_final/README.md)。
