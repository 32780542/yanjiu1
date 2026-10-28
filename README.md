# 多车道纯规则编队研究

当前工作目录为 `D:\yanjiu1\keyan1`，运行入口为 `runrun.py`。车辆依据本车观测、私有记忆和明确的条件规则，完成纵向跟驰与分层补位。道路支持 2、3、4 车道，相邻车道交错 15 m，同车道默认间距 30 m。

## 从哪里开始读

- [纯规则编队系统说明](docs/纯规则编队系统说明.md)：研究进展、系统组成、全部规则、参数、公式和执行顺序。
- [系统方法索引](docs/纯规则系统方法索引.md)：当前运行链路的 419 个函数、类和显式类方法，逐项链接到源码。
- [存储整理报告](docs/存储整理报告.md)：空间占用、已实施优化和 GitHub 版本管理方式。
- [仅NOA误计与大流量小车组诊断](docs/仅NOA误计与大流量小车组诊断.md)：当前结论、逐帧结构复查、追赶与补位失效原因。
- [直路NOA与局部几何匹配报告](docs/直路NOA与编队规模稳定度报告.md)：修正后54例数值、三组图及识别口径更正。
- [基础NOA与入口修正规则](docs/基础NOA与入口修正规则.md)：当前跟驰、共同应急保护、巡航设定与物理上游段。
- [局部几何匹配评价](docs/编队规模与稳定度评价.md)：原指标定义、公式及其与完整编队的区别。
- [历史持续交通流报告](docs/持续大交通流验证报告.md)：修正前54例原始结果与常规组偏慢的原因。
- [持续交通流评价方法](docs/持续交通流评价方法.md)：MATLAB来车机制、配对设置、时间与燃油公式、文献依据。
- [多工况验证报告](docs/编队多工况验证报告.md)：2026-10-28 完成的 65 例随机车流实验、结果图表和适用条件。
- [编队效果评价标准](docs/编队效果评价标准.md)：四类指标、精确判据、公式和本机文献页码。
- [历史实验评价](docs/phase5g_evaluation_2026-09-28.md)：9 月的 39 例实验协议和历史记录。
- [阶段检查点](docs/phase5_checkpoint.md)：按时间记录的实现、验证和接续位置。

## 运行窗口仿真

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
python -B runrun.py --check
python -B runrun.py
```

程序先打开 SUMO-GUI，再逐拍计算和显示。每计算完 0.1 s 的轨迹，窗口显示这一帧，确认后继续下一帧。顶部配置默认三车道、12 辆车、seed 1、目标速度 10 m/s、总观察时长 200 s。`WAIT_BEFORE_CLOSE=True` 时，结束后等待 Enter。

本机使用 Python 3.12 与 SUMO 1.27.1。程序通过 `SUMO_HOME`、`configs/tools.json` 或 PATH 定位 SUMO。`--check` 会打印实际使用的 GUI、TraCI、路网和配置。

## 当前代码怎样组织

| 文件 | 职责 |
| --- | --- |
| `runrun.py` | 用户配置和运行入口。 |
| `variants/phase5g_pure_formation/noa/simple_formation.py` | 跟驰目标、直接观察各车道四层占位、唯一补位候选。 |
| `variants/phase5g_pure_formation/noa/simple_controller.py` | 候选稳定、锚点维护、纵向动作、逐车道换道与到位确认。 |
| `variants/phase5g_pure_formation/noa/driving.py` | 基础巡航、前车约束和道路终点停车计算。 |
| `variants/phase5g_pure_formation/noa/controller.py` | 公共控制入口及历史策略兼容路径。 |
| `variants/phase5g_pure_formation/perception/` | 本车有限范围观测和局部道路。 |
| `variants/phase5g_pure_formation/models/` | 运动学模型、执行器和贝塞尔参考。 |
| `variants/phase5g_pure_formation/simulation/` | 动态发车、同拍快照和统一推进。 |
| `variants/phase5g_pure_formation/experiments/` | 参数装配、单次运行、固定矩阵、评价与重放。 |
| `demo/sumo_gui.py` | 子进程连接、逐帧显示和运行记录。 |

每车观测范围为前方 200 m、后方 100 m、横向两侧各 50 m。纵向相邻间隔不超过 50 m 的可见车辆组成局部车群；换道使用本车前后 90 m 的四层窗口。同车道跟驰使用完整可见连通车群。另一车道某层是否有车，由那个车道的可见物理占位直接判断。

## 研究进展与本轮整理

阶段5G的运动、感知、跟驰、补位、实时显示和评价链路已经实现。本轮修正基础NOA的虚假制动，统一两种模式的车身候选和闭合速度应急保护，编队期望速度封顶共同巡航设定。持续车流增加−300 m物理上游段，拆分源端放行、测量入口与出口，避免用短空隙人为制造低速插入。

原评价器输出的是局部几何匹配规模、参与率、误差和关系保持，并未验证完整多层编队。详见最新诊断。修正后的54例600s工况全部完成、排空，接触与越界均为0；141项受影响回归和完整链路150项通过。378个文件摘要、41282条计划车辆台账及全部指标已独立复算。

三车道直路中，仅NOA通过1200m为41.67s，编队规则组41.71–41.85s。原2.21–2.47辆均值和最大8辆均为局部几何匹配分量，撤回其作为完整编队规模成果的表述。逐帧复查发现：仅NOA只有偶然的单层匹配；1750/2000需求的6个编队实验补位换道均为0，完整多层队形尚未形成。共同巡航封顶使同速后车无法追近，补位门又等待周围先排好，需要修正规则。便携原统计在`docs/experiments/2026-10-28-noa-platoon`，结构复查在`docs/experiments/2026-10-28-platoon-diagnosis`。

持续车流批量入口：

```powershell
python -B scripts/run_logged.py --label continuous-traffic --timeout 7200 -- python -X faulthandler -B variants/phase5g_pure_formation/run_traffic_flow.py --workers 16
```

旧版54例、41282条台账、324摘要及图表保留在`docs/experiments/2026-10-28-continuous-traffic`。该版两组纵向约束与实际速度不同，其较大效率改善率是历史实现诊断，不作为修正后编队的效果结论。

同日先前完成65例有限车群验证：2/3/4车道、每车道252/756/1512辆/h、5个种子，以及目标速度和同车道层距变化。57/65例形成，全部记录完整，无车体碰撞。较密集来车下形成较稳定；稀疏来车的远距车群和部分占位调整仍有未形成案例。完整数字见多工况报告。

有限车群批量入口：

```powershell
python -B variants/phase5g_pure_formation/run_formation_study.py --workers 6
```

新入口采用 MATLAB 式逐车道 Bernoulli 请求和安全入口队列，保存压缩物理轨迹。跟驰与换道规则保持当前版本。四类指标由轨迹独立复算；本轮数据、CSV 和 PNG/SVG 图表位于 `docs/experiments/2026-10-28-formation`。完整本机原始批次约 54.2 MiB，路径见报告。

2026 年 10 月 26 日完成代码职责拆分和存储整理：

- 600 个局部场景及 2/3/4 车道共 1250 拍闭环记录的完整输出摘要，与整理前一致。
- 完整编队回归 150 项、GUI 与审计 91 项、多车道与检测 41 项通过。
- 实际运行三车、15 s 的 SUMO-GUI，完成 151 帧，碰撞和传送为 0。
- 历史结果与临时验证数据采用无损压缩，节省约 4.6 GiB。
- 新轨迹采用紧凑 JSON，字段、数值精度和积分子步完整保留。

## 版本和数据

源码、配置、测试和文档保存在 [32780542/yanjiu1](https://github.com/32780542/yanjiu1)。本地远端 `yanjiu1` 对应这个仓库，目标分支为 `main`；另一个 `origin` 指向历史仓库。

代码版本使用 Git 提交管理。大型轨迹写入被忽略的结果目录，由实验编号与结果摘要索引；历史失败和未完成记录与成功记录一起保留。日常接续先读系统说明，再读检查点末尾，然后定位具体规则函数。
