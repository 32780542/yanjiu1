# 局部感知的交错编队形成与车道减少变换

工作目录：`D:\yanjiu1\keyan1`。现行方法为 **D1**：真实前车固定时距跟驰维持纵向运动，相邻道实车互选维持交错形状，实际间隙与未来车道负荷共同决定横向分工。三道减为两道时，接收道车辆提前向空余存续道分担，为终止道的必要合流留下空间。

规则集中在一个 **423行** 文件，较上一版S减少38行。每车只读取前200米、后100米内各车道车辆的实测状态及三个本车记忆字段。巡航28.8m/s，最高33.3m/s；巡航同道30米、相邻道交错15米。控制没有中心排序、邻车私有状态或全局评价反馈。

## 当前研究结果

本轮只测试 **1500、1750、2000辆/h/车道**。冻结规则后，用91–95五个新种子，在三车道直路与3→2道路比较NOA、原编队S和D1，共90例。全部正常排空、无碰撞和传送，逐车时间、共同需求、物理参数与源码经独立复算。

| 每道流量 | NOA缩道系统时间(s) | D1缩道系统时间(s) | D1改善 | 扣除直路改善后的额外缩道节省(s/车) |
| ---: | ---: | ---: | ---: | ---: |
| 1500 | 42.444 | 41.930 | 1.21% | 0.096 |
| 1750 | 43.253 | 42.345 | 2.09% | 0.404 |
| 2000 | 44.715 | 43.234 | 3.30% | 0.915 |

15组缩道对比均更快；额外缩道节省分别有4/5、4/5、5/5种子为正。81/82种子另持续来车1800秒，三档系统时间改善1.09%、2.05%、4.37%。600秒与1800秒结果分别汇总。

实际轨迹显示640米前完成的中道1→0腾位，必要合流的长尾延误减少。**燃油仍高于NOA，急减速未全面改善。** 相对原编队S，D1正式缩道系统时间再减少0.179、0.255、0.582秒/车，燃油均值也降低。完整数据与消融见[研究报告](docs/experiments/2026-11-03-midflow-staggered/README.md)。

## 下次接续从哪里读

1. [完整系统说明与规则集](docs/原生SUMO编队变换系统说明.md)：逐条规则、全部方法、参数、状态、执行顺序与指标。
2. [本轮研究报告](docs/experiments/2026-11-03-midflow-staggered/README.md)：正式对照、持续流、消融、实际队形、未采用方案。
3. [论文主线与贡献](docs/experiments/2026-11-03-midflow-staggered/论文主线与贡献.md)：研究问题、与Cai的关系、统一方法逻辑及证据安排。
4. [恢复检查点](docs/phase5_checkpoint.md)：开头最新入口与末尾执行记录，不用重跑历史前置验收。
5. [24辆形成和45辆变换](docs/experiments/2026-11-03-staggered-bottleneck/formation_demo_D1/README.md)：实际位置、时距、交错误差及可复算图。
6. [本轮文献依据](docs/experiments/2026-11-03-midflow-staggered/literature/README.md)、[MATLAB调用链](docs/2026-10-29-MATLAB车辆控制调用链核查.md)。

## 打开实时仿真窗口

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
python -B runrun.py --check
python -B runrun.py
```

也可在VS Code直接运行这个目录里的`runrun.py`。SUMO窗口与第一次计算同步，每算0.1秒推进一步。默认每道1750辆/h、600秒、seed1，配置在脚本顶部。`--gui-delay-ms 0`加快显示，`--no-wait`结束后自动关闭。

路网0–1000米为三道，1000–1200米为两道，准备区从640米开始。观察接收道向lane0腾位、lane2进入lane1以及后续两道交错恢复。跟驰距离为`D(v)=5.5+0.8506944444v`，巡航时对应30米/15米。45辆完整两道队形跨度较长，几何展示另用2400米道路；交通效率仍在原1200米道路比较。

```powershell
python -B runrun.py --headless --duration 20 --max-time 120 --no-wait
python -B variants/phase5g_pure_formation/run_native_flow.py --mode noa --flow 1750 --duration 600 --max-time 1200
python -B variants/phase5g_pure_formation/run_native_flow.py --mode transform --flow 1750 --duration 600 --max-time 1200
```

## 代码结构与验收

| 文件 | 职责 |
| --- | --- |
| [runrun.py](runrun.py) | 用户配置、实时窗口、自检 |
| [native_rules.py](variants/phase5g_pure_formation/noa/native_rules.py) | 纯规则控制、本车三个记忆字段、关联状态0/1 |
| [native_sumo.py](variants/phase5g_pure_formation/experiments/native_sumo.py) | 伯努利来车、局部观测、原生执行和记录 |
| [run_native_flow.py](variants/phase5g_pure_formation/run_native_flow.py) | 单次实验与固定矩阵入口 |
| [native_comparison.py](variants/phase5g_pure_formation/experiments/native_comparison.py) | 共同条件核验、逐车重算与配对 |
| [实验工具](docs/experiments/2026-11-03-staggered-bottleneck/tools/README.md) | 冻结、紧凑封存与离线复算 |

`formation_state=1`表示本车已有实际编队关系，允许仍在调距；纯NOA为0。同时参与人数可包含多支队伍，实际队形另按轨迹检查。

已安装源码SHA256：`2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a`。[实际磁盘验收](docs/experiments/2026-11-03-midflow-staggered/implementation/installed_D1_migrated_core.json)为239项测试及51项子测试通过；9项GUI入口测试、自检及30/30辆真实SUMO短测也通过。独立审查与测试迁移原件均保留。

版本保存在[GitHub](https://github.com/32780542/yanjiu1)。远端`yanjiu1`对应本仓库，`origin`是历史仓库。本轮分支为`research/20261103-midflow-staggered`；候选保存小补丁与SHA，完整计划分组紧凑归档。成功大轨迹经原件、归档和机制核验后定点清理，代表性完整轨迹和失败原件保留。

本轮已释放约1.70GB，包括1.55GB可替代成功轨迹和0.15GB已归档诊断的重复展开文件。120个案例的完整轨迹、反向结果上下文和24/45队形原件继续保留，见[存储执行记录](docs/experiments/2026-11-03-midflow-staggered/cleanup_execution/README.md)。

旧[S报告](docs/experiments/2026-11-03-staggered-bottleneck/README.md)、[TM报告](docs/experiments/2026-10-30-rule-trials/研究结果与采用说明.md)和[Cai原文对照](docs/Cai2024全局方案对照依据.md)保留各自版本含义；当前结论以本轮三档流量与D1为准。
