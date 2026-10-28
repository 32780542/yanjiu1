# 多车道纯规则编队与车道减少变换

工作目录是 `D:\yanjiu1\keyan1`。当前主线使用真实SUMO发车和运动：每车观察前200米、后100米内所有车道的实车，用本车私有记忆和条件规则形成交错编队，完成3→2变换。巡航28.8m/s、最高33.3m/s，同道期望间距30米，相邻车道交错15米。

## 接续研究先读什么

1. [现行系统说明](docs/原生SUMO编队变换系统说明.md)：逐条解释全部规则、方法、代码结构、执行顺序、参数与指标。
2. [本轮验证报告](docs/2026-10-29-原生编队变换验证报告.md)：600秒配对实验、交通效率、燃油、编队规模、稳定性与Cai对照。
3. [阶段检查点](docs/phase5_checkpoint.md)：从末尾恢复实际运行、测试和未完成事项。
4. [方法迭代记录](docs/2026-10-29-编队变换方法更新.md)：保留失败轨迹和被替换的方法，不作为现行规则定义。
5. [Cai2024对照依据](docs/Cai2024全局方案对照依据.md)：原图读数、MATLAB细节及本机集中参考的定义。

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

`noa`为普通自主行驶，`formation`为编队加普通合流，`transform`为编队加局部变换，`global`为Cai式集中分配参考。只有global读取全体实车表和联合分配目标；其他方案的控制器只接收有限局部观测。

## 方法怎样工作

同道只跟随实际前车的位置和速度，目标位于其后30米。没有同道前车的头车，以28.8m/s为基础，按其他车道头车的位置误差最多上下调整2m/s，对齐各道首层。短单元可临时追近前方车群；跨道对齐不复制邻车速度。

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

迭代修复了跨道矛盾引用环、虚拟合并车道排名、横移目标丢失、过期物理间隙和必要合流争隙。位置增益为0.3，速度反馈每步权重0.2（0.5秒名义响应时间）；统一当前位置F/R空隙，删除普通合流30米候选门。[校准表](docs/experiments/2026-10-29-native-pd-final/calibration.csv)保留37个校准探针及其未完成结果。本版156项核心检查通过，六车经3次实际换道安全恢复两道三层。

D40已全部完成并独立复算：四方案×五种子×两种道路，每次600秒来车，随后排空。[协议](docs/experiments/2026-10-29-native-pd-final/protocol.json)记录参数和源码摘要。40例均安全排空，0碰撞/瞬移；3→2五种子的平均行程40.971秒，NOA为42.024秒（缩短2.50%）。下游完整编队参与25.25%，峰值12辆；油耗增加31.93%。完整表、逐种子差值及Cai原图对照见本轮验证报告。

评价包括行程与系统时间、发车延迟、出口流量、燃油g/km、实际合流完成和编队质量。主规模至少有两个完整连续层，每层每道均有实车，内部不能漏车。位置容差2米、速度差0.5m/s，连续1秒确认，5秒关系保持另报。仅NOA的偶然几何排列与受控编队区分记录。

历史2/3/4车道、多流量实验采用此前自写运动学链路，见[多工况报告](docs/编队多工况验证报告.md)与[旧直路诊断](docs/直路NOA与编队规模稳定度报告.md)。现行原生链路验证三道直路和3→2；历史与失败数据继续保留。

## 版本、数据与复算

源码、测试、文档和小体积成果保存在 [32780542/yanjiu1](https://github.com/32780542/yanjiu1)。本地远端 `yanjiu1` 对应该仓库和main分支；`origin`是历史仓库。

每次结果有独立目录，保存请求、源码快照、参数、SUMO版本、逐车账本、0.1秒压缩轨迹和事件。大型原始数据以gzip留在被忽略的results目录，由运行编号与摘要索引，不另复制整份项目作为版本。本轮A/C/D方法数据、Cai图读数和科研图形约5.8MB；恢复逐车明细用无损gzip，紧凑摘要用于直接阅读。

重跑矩阵：

```powershell
python -B scripts/run_logged.py --label native-validation --timeout 3600 -- python -B variants/phase5g_pure_formation/run_native_flow.py --matrix --seeds 1 2 3 4 5 --scenarios lane_drop straight3 --flow 1250 --duration 600
```

接续任务时读本README、现行系统说明及检查点末尾，再读实际代码和对应账本。