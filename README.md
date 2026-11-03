# 局部感知的时距交错编队与车道收缩

工作目录：**D:\yanjiu1\keyan1**。当前研究版本为 **C12：时距交错形成与单向收缩**，316行规则集中在 [native_rules.py](variants/phase5g_pure_formation/noa/native_rules.py)。每辆车根据前200米、后100米内各车道车辆的实际运动和自身记忆，计算自己的速度与换道动作。

同道目标车头间距为 **D(v)=5.5+0.85v 米**，相邻道错开半D。巡航28.8 m/s时，对应29.98米与14.99米。三道变两道时，终止道车辆进入相邻存续道，中道车辆沿实际交错空位向另一存续道接续；每次横移都向存续方向进行。

## 从这里了解当前工程

1. [系统说明](docs/原生SUMO编队变换系统说明.md)：方法目的、执行流程、代码结构和运行方法。
2. [逐条规则与全部函数](docs/experiments/2026-11-04-timegap-staggered/规则逐条说明.md)：每条跟驰、形成、接收、换道、安全规则的条件、动作与源码位置。
3. [本轮研究进展](docs/experiments/2026-11-04-timegap-staggered/README.md)：采用和未采用的版本、实际数据及当前结论。
4. [评价口径](docs/experiments/2026-11-04-timegap-staggered/evaluation.md)：交通效率、油耗、直接0/1参与统计与真实队形指标。
5. [论文主线与证据安排](docs/experiments/2026-11-04-timegap-staggered/论文主线与证据安排.md)：研究问题、贡献、对照和图表安排。
6. [执行检查点](docs/phase5_checkpoint.md)：从末尾读取最新已完成工作、正在运行的批次和下一入口。

方法来源见 [本轮依据](docs/experiments/2026-11-04-timegap-staggered/method_options.md) 和 [150篇文献库](docs/research/2026-10-30-literature-review/README.md)。文献库分别标明相关章节、摘要预览和仅题录的读取深度；采用细节以当前规则为准。

**本轮仍在进行，截止为2026年11月4日08:00。** 最终C12于04:35登记锁定，211–215独立五种子的正式主135例已全部安全排空；并排及参数、机制补充继续进行。开发结果与正式确认分别保存。

## 当前已经验证到哪里

45车几何演示中，C12完成22次横移、每车最多一次，在全45车仍在场时恢复两道完整交替。70秒色序闭合；80、90、100秒的相邻半D间距平均绝对误差分别约0.0594、0.00420、0.000328米。该演示把出口延长到3600米，给队形恢复留下观察距离；交通比较始终使用原1200米道路。

C12在50米内建立普通跟驰链，之后可在200米内继续跟当前真实前车。前车因切入或离开而替换时保持这条纵向链；实际前车消失时释放关系。相同高流量开发样本的上游相位误差由C8的约11.1米降至5.6米。

正式600秒来车试验中，C12在相同道路信息下的30个缩道配对全部快于反应式NOA。下表为五种子等权均值的时间减少；括号内为两组均值之比计算的下降百分比。

| 流量(辆/h/道) | 200米直接感知 | 300米公共预告 |
| ---: | ---: | ---: |
| 1500 | 4.15秒（9.27%） | 4.21秒（9.45%） |
| 1750 | 6.54秒（13.62%） | 6.59秒（13.85%） |
| 2000 | 9.67秒（17.31%） | 10.85秒（19.70%） |

相同需求的直路时间差在约0.11秒以内，瓶颈区域的低速和末道停止暴露明显减少；收益主要出现在缩道条件。低流量油耗增加，高流量600秒结果接近NOA；1800秒两种子持续对照的六格平均油耗仍增加，均保留实际数值。完整指标见[正式主结果](docs/experiments/2026-11-04-timegap-staggered/formal600_main_summary.md)与[1800秒结果](docs/experiments/2026-11-04-timegap-staggered/C12_long1800_summary.md)。

交错相对匹配并排的独有作用，以及共同速度上限下的效果，按独立补充对照报告。45车控制探针的平均瓶颈延误小幅改善，最后一辆通过略晚；它与持续随机交通分别解释，详见[机制探针](docs/experiments/2026-11-04-timegap-staggered/stage/cohort_mechanism_report/report.md)。

仅形成而不主动变换的方案、纯NOA、形成并变换的方案分开运行。车辆输出的状态1只表示本车已有编队关系，允许仍在调距；NOA始终为0。状态1的总人数与真实交错几何分别评价。

## 打开实时SUMO窗口

在VS Code运行本目录的 `runrun.py`，或执行：

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
python -B runrun.py --check
python -B runrun.py
```

窗口与第一次计算同步：每计算一步，SUMO推进0.1秒。默认每道1750辆/h、来车600秒、seed1。默认道路为0–1000米三道、1000–1200米两道；本车在离终止位置200米时直接看到缩道。

```powershell
python -B runrun.py --duration 60 --max-time 240 --gui-delay-ms 20 --no-wait
python -B runrun.py --headless --duration 20 --max-time 150 --no-wait
python -B variants/phase5g_pure_formation/run_native_flow.py --mode noa --flow 1750 --duration 600 --max-time 1200
python -B variants/phase5g_pure_formation/run_native_flow.py --mode transform --flow 1750 --duration 600 --max-time 1200
```

观察lane2退入lane1、部分lane1车辆移入lane0，以及下游两道的纵向错位恢复。200米直接可见与300米公共道路预告作为两个独立实验条件；公共预告对所有对照方法同时提供，邻车感知范围不随之扩大。

## 代码结构

| 文件 | 工作 |
| --- | --- |
| [runrun.py](runrun.py) | 常用参数、实时窗口和自检 |
| [native_rules.py](variants/phase5g_pure_formation/noa/native_rules.py) | 数据类、跟驰、互选错位、实际空位、局部收缩与安全速度 |
| [native_sumo.py](variants/phase5g_pure_formation/experiments/native_sumo.py) | 来车、局部跟踪、原生SUMO执行、逐步记录 |
| [run_native_flow.py](variants/phase5g_pure_formation/run_native_flow.py) | 单次实验命令行入口 |
| [native_comparison.py](variants/phase5g_pure_formation/experiments/native_comparison.py) | 同输入比较与逐车统计 |
| [本轮实验工具](docs/experiments/2026-11-04-timegap-staggered/tools) | 表格消费与实际轨迹绘图 |
| [受影响测试](variants/phase5g_pure_formation/tests/run_native_contracts.py) | 明确模块的真实磁盘合同入口 |

每车只保存自己的目标道与主前驱关联；执行空位接续时，前驱字段优先保存空位锚车。控制器不读取全局编队表、其他车辆的私有状态或统计结果。记录器可以读取全路轨迹，用于科研评价。

## 版本与历史

版本管理使用 [GitHub仓库](https://github.com/32780542/yanjiu1)，远端名为 `yanjiu1`；`origin`是历史仓库。本轮分支为 `research/20261104-timegap-staggered`。代码候选只保留小型规则源与变更，实验复用同一组引擎文件，不复制整套项目。

11月3日D1及其负荷/成本规则保存在 [D1历史报告](docs/experiments/2026-11-03-midflow-staggered/README.md) 和Git历史中。其数据属于当时方法与基线，不能与当前C8结果合并。此前定点清理已释放约1.70GB；本轮新增数据的实际归档和清理状态以本轮报告为准。

[Cai原文对照依据](docs/Cai2024全局方案对照依据.md)保留原论文图、当前MATLAB调用链与可比条件。当前没有Cai发表版在本轮相同条件下的行程时间或油耗标量。
