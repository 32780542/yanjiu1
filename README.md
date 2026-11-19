# 局部感知的时距交错编队与车道收缩

当前版本在三车道上形成交错队形，遇到缩道后将同一批车辆重排为两道交错队形。每辆车观察前 200 米、后 100 米内各道实车，自行选择相邻车道并调整速度。速度相关的同道间距为 $D(v)=5.5+0.85v$ 米，两道相邻车辆错开半个间距。两道重排时，各车按自己看到的前后顺序交替选道，再把实车位置拟合到等距队形上。[当前完整规则、数学模型与验证](docs/experiments/2026-11-19-staggered-reconfiguration/README.md) · [控制器源码](variants/phase5g_pure_formation/noa/native_rules.py)

在 `D:\yanjiu1\keyan1` 运行 `python runrun.py --transform-demo`。12 辆车从三道 6/4/2 出发，在同一条路上排成 4/4/4，再通过缩道排成 6/6。运行 `python runrun.py` 看连续车流，运行 `python runrun.py --formation-demo` 单看三道形成。[2026.11.19 第一版云端存档](https://github.com/32780542/yanjiu1/tree/2026.11.19-v1)

11 月 4 日续跑比较了 300、500、600 米公共预警，并检验了提前空位规则 L6。阶段报告包含五种子配对、1800 秒持续流、两种固定车群初态、候选代码和窗口运行命令。 [公共预警续跑报告](docs/experiments/2026-11-04-public-preview/README.md)

## 历史基准与工程资料

1. 从一次逐帧决策读到每个辅助函数，见[11 月 18 日规则与源码阅读](docs/experiments/2026-11-18-local-bottleneck/代码阅读.md)。
2. 查三种流量的纯 NOA、局部交错、简化集中式实测数据，见[本轮研究报告](docs/experiments/2026-11-18-local-bottleneck/README.md)。
3. 看一串真实换道如何发生，以及只形成队形、启动变换和限制引导前车的区别，见[变换机制与消融](docs/experiments/2026-11-18-local-bottleneck/变换机制.md)。
4. [评价口径](docs/experiments/2026-11-04-timegap-staggered/evaluation.md)：交通效率、油耗、直接0/1参与统计与真实队形指标。
5. [论文主线与证据安排](docs/experiments/2026-11-04-timegap-staggered/论文主线与证据安排.md)：研究问题、贡献、对照和图表安排。
6. [执行检查点](docs/phase5_checkpoint.md)：从末尾读取最新已完成工作、正在运行的批次和下一入口。
7. [交错与并排的四组对照、纯 HDV 的全程时间](docs/experiments/2026-11-18-local-bottleneck/factorial_hdv.md)。含普通 HDV 的实时仿真命令，以及两套道路环境的逐车数据。

方法来源见 [本轮依据](docs/experiments/2026-11-04-timegap-staggered/method_options.md) 和 [150篇文献库](docs/research/2026-10-30-literature-review/README.md)。文献库分别标明相关章节、摘要预览和仅题录的读取深度；采用细节以当前规则为准。

**11 月 4 日试验已完成。** 冻结 C12 于2026年11月4日04:35登记锁定，之后保持不变。正式主135例、匹配并排45例、1800秒持续24例、扩展NOA45例、共同速度上限36例、时距敏感性48例，共333条持续交通及补充实验，全部安全排空。六条固定车群几何另计；开发结果与正式确认分别保存。

## 11 月 4 日冻结版 C12 的验证

45车几何演示中，C12完成22次横移、每车最多一次，在全45车仍在场时恢复两道完整交替。70秒色序闭合；80、90、100秒的相邻半D间距平均绝对误差分别约0.0594、0.00420、0.000328米。该演示把出口延长到3600米，给队形恢复留下观察距离；交通比较始终使用原1200米道路。

C12在50米内建立普通跟驰链，之后可在200米内继续跟当前真实前车。前车因切入或离开而替换时保持这条纵向链；实际前车消失时释放关系。相同高流量开发样本的上游相位误差由C8的约11.1米降至5.6米。

正式600秒来车试验中，C12在相同道路信息下的30个缩道配对全部快于反应式NOA。下表为五种子等权均值的时间减少；括号内为两组均值之比计算的下降百分比。

| 流量(辆/h/道) | 200米直接感知 | 300米公共预告 |
| ---: | ---: | ---: |
| 1500 | 4.15秒（9.27%） | 4.21秒（9.45%） |
| 1750 | 6.54秒（13.62%） | 6.59秒（13.85%） |
| 2000 | 9.67秒（17.31%） | 10.85秒（19.70%） |

相同需求的直路时间差在约0.11秒以内，瓶颈区域的低速和末道停止暴露明显减少；收益主要出现在缩道条件。低流量油耗增加，高流量600秒结果接近NOA；1800秒两种子持续对照的六格平均油耗仍增加，均保留实际数值。完整指标见[正式主结果](docs/experiments/2026-11-04-timegap-staggered/formal600_main_summary.md)与[1800秒结果](docs/experiments/2026-11-04-timegap-staggered/C12_long1800_summary.md)。

交错在30个缩道配对中有22个略快，两种几何的时间差较小，当前收益主要由关系接续与提前收缩解释。把NOA真实前车跟驰范围扩到200米后，C12仍在27/30个缩道配对更快，高流量分别节省8.44和9.00秒；把双方指令速度上限共同设为28.8 m/s后，另两种子的12个缩道配对也全部更快。详见[并排消融](docs/experiments/2026-11-04-timegap-staggered/formal600_parallel_summary.md)、[扩展NOA](docs/experiments/2026-11-04-timegap-staggered/posthoc_NOAfront200_summary.md)与[共同速度上限](docs/experiments/2026-11-04-timegap-staggered/posthoc_speedcap288_summary.md)。45车控制探针的平均瓶颈延误小幅改善，最后一辆通过略晚；它与持续随机交通分别解释，详见[机制探针](docs/experiments/2026-11-04-timegap-staggered/stage/cohort_mechanism_report/report.md)。

时距0.75 s和1.0 s的48例也全部完成，12个缩道模式配对均显示变换收益；但1.0 s相对0.75 s在2000流量下使编队系统时间增加16.87秒。参数增大带来的空间占用与效率代价，和同参数下的编队收益分别评价，详见[时距敏感性](docs/experiments/2026-11-04-timegap-staggered/posthoc_headway_summary.md)。

仅形成而不主动变换的方案、纯NOA、形成并变换的方案分开运行。车辆输出的状态1只表示本车已有编队关系，允许仍在调距；NOA始终为0。状态1的总人数与真实交错几何分别评价。

11 月 4 日冻结 C12 的受影响148项测试通过；根入口实时GUI的20秒来车演示30/30辆安全完成。[原始测试与窗口记录](docs/experiments/2026-11-04-timegap-staggered/data/verification/README.md)已保存；独立复核结论见[最终证据验收](docs/experiments/2026-11-04-timegap-staggered/stage/final_evidence_review.md)。

## 打开实时SUMO窗口

在VS Code运行本目录的 `runrun.py`，或执行：

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
python -B runrun.py --check
python -B runrun.py
```

窗口随第一次计算逐步推进，每步0.1秒。你可以手动平移和缩放，运行器不会自动重设镜头。默认每道 2000 辆/h、来车 600 秒、种子 6。默认道路为0–1000米三道、1000–1200米两道；本车在离终止位置200米时直接看到缩道。

```powershell
python -B runrun.py --duration 60 --max-time 240 --gui-delay-ms 20 --no-wait
python -B runrun.py --headless --duration 20 --max-time 150 --no-wait
python -B variants/phase5g_pure_formation/run_native_flow.py --mode noa --flow 1750 --duration 600 --max-time 1200 --gui
python -B variants/phase5g_pure_formation/run_native_flow.py --mode transform --flow 1750 --duration 600 --max-time 1200 --gui
```

在道 2 结束后，可沿道 0 和道 1 观察车辆如何交替占位。当前入口使用 200 米直接视距。公共道路预告的历史试验见上方报告。

## 代码结构

| 文件 | 工作 |
| --- | --- |
| [runrun.py](runrun.py) | 常用参数、实时窗口和自检 |
| [native_rules.py](variants/phase5g_pure_formation/noa/native_rules.py) | 局部观测、三道形成、两道几何投影与安全速度 |
| [native_sumo.py](variants/phase5g_pure_formation/experiments/native_sumo.py) | 来车、局部跟踪、原生SUMO执行、逐步记录 |
| [run_native_flow.py](variants/phase5g_pure_formation/run_native_flow.py) | 单次实验命令行入口 |
| [native_comparison.py](variants/phase5g_pure_formation/experiments/native_comparison.py) | 同输入比较与逐车统计 |
| [本轮实验工具](docs/experiments/2026-11-18-local-bottleneck/tools) | 同输入对照、轨迹分析、位置统计与速度时空图 |
| [受影响测试](variants/phase5g_pure_formation/tests/run_native_contracts.py) | 明确模块的真实磁盘合同入口 |

每车保有自身横移进度和局部参考车跟踪号。记录器另外采集全路轨迹，用于测量队形与行程。

## 版本与历史

当前研究分支为 `research/20261118-local-bottleneck`，远端名为 `yanjiu1`。11 月 4 日的 C12 对照保存在对应的研究分支和固定证据中。日常入口为根目录的 `runrun.py`，复算历史实验时按各实验登记的提交和参数运行。[GitHub 仓库](https://github.com/32780542/yanjiu1)

11月3日D1及其负荷/成本规则保存在 [D1历史报告](docs/experiments/2026-11-03-midflow-staggered/README.md) 和Git历史中。其数据属于当时方法与基线，与当前C12分别保存。本轮已在云端归档核验后，定点释放1,650,262,592字节原始大轨迹；这是实际删除文件之和，新增实验数据另计。关键逐步轨迹、失败和未完成记录保留，见[数据与存储说明](docs/experiments/2026-11-04-timegap-staggered/data/evidence/README.md)。此前约1.70GB清理属于上一轮，不重复计入本轮。

[Cai原文对照依据](docs/Cai2024全局方案对照依据.md)保留原论文图、当前MATLAB调用链与可比条件。当前没有Cai发表版在本轮相同条件下的行程时间或油耗标量。
