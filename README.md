# 多车道纯规则编队与车道减少变换

当前主代码保留P的驾驶规则，新增本车输出的`formation_state=0/1`：已有局部编队跟驰、被跟驰或互选队首关系为1，孤立车和纯NOA为0，调距过程也计入。记录器直接汇总参与率、同时参与人数和连续1时长，新运行的常用比较入口不要求完整交错层。实现及验证见[本车状态说明](docs/experiments/2026-10-29-local-formation-state/README.md)。

此前P的[独立验收](docs/2026-10-29-P独立验收报告.md)完成新种子6–10的100例及20例严格消融，全部安全排空，但四个流量均未实现全程交通提效；其中的编队数据采用当时完整层口径。后续R/S候选已否决并单独归档。新增状态未改变车辆运动，原交通结果保留。当前没有正在运行的实验。旧global为自建模型，其数值已退出Cai和最优集中式性能比较。

工作目录是 `D:\yanjiu1\keyan1`。当前主线使用真实SUMO发车和运动：每车观察前200米、后100米内所有车道的实车，用本车私有记忆和条件规则形成交错编队，完成3→2变换。巡航28.8m/s、最高33.3m/s，同道期望间距30米，相邻车道交错15米。

## 接续研究先读什么

1. [现行系统说明](docs/原生SUMO编队变换系统说明.md)：逐条解释全部规则、方法、代码结构、执行顺序、参数与指标。
   本车状态的含义、字段和直接统计见其中第3.13、7.1节。
2. [P独立验收报告](docs/2026-10-29-P独立验收报告.md)：新种子500/750/1000/1500流量的完整交通、编队和消融数据。[D/H校准诊断](docs/2026-10-29-四流量瓶颈归因报告.md)保留旧版结果。
3. [阶段检查点](docs/phase5_checkpoint.md)：从末尾恢复实际运行、测试和未完成事项。
4. [方法迭代记录](docs/2026-10-29-编队变换方法更新.md)：保留失败轨迹和被替换的方法，不作为现行规则定义。
5. [MATLAB 控制调用链](docs/2026-10-29-MATLAB车辆控制调用链核查.md)与[Cai文献依据](docs/Cai2024全局方案对照依据.md)：完整代码的活跃控制链、可借鉴机制及原图记录。
6. [前期方法诊断](docs/experiments/2026-10-29-four-flow-attribution/method_diagnostics/README.md)与[R/S候选档案](docs/experiments/2026-10-29-four-flow-attribution/R_S_diagnostics/README.md)：被否决方法的源码、对照与失败证据。

## 在这个文件夹打开窗口

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
python -B runrun.py --check
python -B runrun.py
```

也可在VS Code中直接运行本文件夹的 `runrun.py`。 当前验证环境为Python 3.12.9与SUMO 1.27.1，`variants/phase5g_pure_formation/configs/tools.json`或`SUMO_HOME`指定SUMO路径。`requirements-tooling.txt`列出已使用的工具版本；SciPy用于集中参考，NumPy和Matplotlib用于绘图。默认每车道1250辆/h、600秒来车、seed 1、局部编队与3→2变换。程序生成路网和发车请求后立即打开SUMO窗口，每计算0.1秒显示一帧，不预先计算整条轨迹。

窗口显示600米道路范围，随前车前移，最后固定600–1200米，可看见640米开始的调整和1000米处的车道终止。结束后在交互终端按Enter关闭并封存。`--gui-delay-ms 100` 让每个仿真步等待100毫秒；`--no-wait` 自动关闭。配置位于 `runrun.py` 顶部。

无窗口短测或单方案运行：

```powershell
python -B runrun.py --headless --duration 20
python -B variants/phase5g_pure_formation/run_native_flow.py --mode noa --duration 600
python -B variants/phase5g_pure_formation/run_native_flow.py --mode transform --duration 600
```

`noa`为普通自主行驶，`formation`为编队加普通合流，`transform`为编队加局部变换，`global`为保留的自建集中分配参考。只有global读取全体实车表和联合分配目标；其他方案的控制器只接收有限局部观测。global不用于声称原Cai算法的性能。

## 方法怎样工作

形成连接限于50米内的实际同道前车，目标位于其后30米。没有这类前车的头车，以28.8m/s为基础，按相邻道互选头车的位置误差最多上下调整2m/s，对齐各道首层。更远车辆仍参与安全判断；跨道对齐不复制邻车速度。双方使用同一个三道或两道构型，具体切换条件见系统说明第3.2节。

自由补位依据实际缺位、车道边界负荷差和物理候选顺序。争取同一层位的车辆使用同一层位附近窗口。横移前和横移中跟踪真实前后车辆构成的间隙；本车越出旧间隙后重新绑定当前位置。实际居中后按新道前车30米入列，纵向收敛后再参与自由补位。

准备区内，中道局部让位，接收车依据可见待并入车辆开隙，终止道车辆利用安全间隙并入。后排车辆已有独立安全走廊时可同时行动。必要合流优先于争同走廊的自由补位和普通超车。各方案共用车型、真实运动和安全执行。

没有Python入口放行门、额外−300米队列或强制轨迹移动。每0.1秒、每车道以概率 `1250×0.1/3600` 请求发车，由SUMO处理实际插入，发车延迟单独记录。

## 当前代码结构

| 文件 | 作用 |
| --- | --- |
| [runrun.py](runrun.py) | 实时窗口、配置、自检。 |
| [native_rules.py](variants/phase5g_pure_formation/noa/native_rules.py) | 跟驰、补位、让位、开隙、合流与私有记忆。 |
| [native_sumo.py](variants/phase5g_pure_formation/experiments/native_sumo.py) | 路网、发车、局部观测、真实执行、逐车和逐拍记录。 |
| [global_reference.py](variants/phase5g_pure_formation/experiments/global_reference.py) | 每5秒集中分组与匈牙利分配。 |
| [complete_layers.py](variants/phase5g_pure_formation/experiments/complete_layers.py) | 完整连续层、规模、参与和保持的物理识别。 |
| [native_comparison.py](variants/phase5g_pure_formation/experiments/native_comparison.py) | 源码与需求核验、逐车重算、配对和汇总。 |
| [run_native_flow.py](variants/phase5g_pure_formation/run_native_flow.py) | 单次和固定矩阵入口。 |

本机Python 3.12、SUMO 1.27.1，集中参考使用SciPy 1.18.1。依赖见 [requirements-tooling.txt](requirements-tooling.txt)。`--check`打印实际SUMO、TraCI和Python依赖位置。

## 本轮进展

修改前代码已通过提交 `26a3de5` 和标签 `backup/pre-lane-drop-20261029` 保存GitHub。已实现原生SUMO链路、局部变换、完整层评价、四方案比较与实时窗口。

迭代修复了跨道矛盾引用环、虚拟合并车道排名、横移目标丢失、过期物理间隙和必要合流争隙。位置增益为0.3，速度反馈每步权重0.2（0.5秒名义响应时间）；统一当前位置F/R空隙，删除普通合流30米候选门。新增状态后通过206项核心测试、29项子测试和9项根GUI测试，900个局部状态及5对真实SUMO运行核实驾驶输出不变。原两个六车诊断均确认六车结构。

最新P使用每道500、750、1000、1500辆/h，600秒连续来车、独立种子6–10。缩减道路的全程平均时间如下：

| 每道流量 / (辆/h) | NOA / s | P编队变换 / s | P−NOA / s |
| ---: | ---: | ---: | ---: |
| 500 | 41.732 | 41.770 | +0.038 |
| 750 | 41.787 | 41.854 | +0.067 |
| 1000 | 41.895 | 41.970 | +0.076 |
| 1500 | 42.661 | 43.597 | +0.936 |

1500下，主要瓶颈段的附加时间减少0.162秒，低速积聚由213.10降为13.68车辆秒；上游成本抵消了局部收益，全程仍更慢，燃油也更高。严格关闭形成跟驰和自由补位的配对消融表明，这两项规则对主要段有贡献，但目前不支持“有效编队带来整体提效”的结论。上游完整多层参与率四个流量均低于1%，持续成队仍是未解决的问题。

早期1250流量D40的全程优势保留在[历史协议与数据](docs/experiments/2026-10-29-native-pd-final/protocol.json)中；后续直路控制与四流量归因否定了原来的瓶颈提效解释。D/H诊断和P独立验收分别封存，不混合种子或版本。

当前评价包括交通时间、燃油、合流完成及本车0/1状态的直接统计。状态参与率按车辆秒加权；同时参与人数为全路总数，连续1的时长反映关系保持。旧报告的完整层规模、1秒确认及5秒保持是另一套历史几何口径，原数据继续保留。多支编队各自大小需要队伍关系信息，本次的0/1总人数不作单支编队规模解释。

历史2/3/4车道、多流量实验采用此前自写运动学链路，见[多工况报告](docs/编队多工况验证报告.md)与[旧直路诊断](docs/直路NOA与编队规模稳定度报告.md)。现行原生链路验证三道直路和3→2；历史与失败数据继续保留。

## 版本、数据与复算

源码、测试、文档和小体积成果保存在 [32780542/yanjiu1](https://github.com/32780542/yanjiu1)。本地远端 `yanjiu1` 对应该仓库和main分支；`origin`是历史仓库。

每次结果有独立目录，保存请求、源码快照、参数、SUMO版本、逐车账本、0.1秒压缩轨迹和事件。大型原始轨迹留在被忽略的results目录，由运行编号与SHA-256索引；Git保存紧凑无损数据包和去重源码档案，不另复制整份项目作为版本。[本轮成果目录](docs/experiments/2026-10-29-four-flow-attribution)中的portable_D_baseline/H/C0/C1/P/C1_P分别保存各版表格、逐次结果、请求及源码。便携包内verify_portable.py用于检查公开包，部分验证还需本机保留的原轨迹；包内说明列出范围。

重跑当前P的四流量矩阵：

```powershell
python -B scripts/run_logged.py --label four-flow-replication --timeout 7200 -- python -B variants/phase5g_pure_formation/run_flow_study.py --flows 500 750 1000 1500 --seeds 6 7 8 9 10 --jobs 4
```

接续任务时读本README、现行系统说明及检查点末尾，再读实际代码和对应账本。
