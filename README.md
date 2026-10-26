# 多车道纯规则编队研究

当前工作目录为 `D:\yanjiu1\keyan1`，运行入口为 `runrun.py`。车辆依据本车观测、私有记忆和明确的条件规则，完成纵向跟驰与分层补位。道路支持 2、3、4 车道，相邻车道交错 15 m，同车道默认间距 30 m。

## 从哪里开始读

- [纯规则编队系统说明](docs/纯规则编队系统说明.md)：研究进展、系统组成、全部规则、参数、公式和执行顺序。
- [系统方法索引](docs/纯规则系统方法索引.md)：当前运行链路的 419 个函数、类和显式类方法，逐项链接到源码。
- [存储整理报告](docs/存储整理报告.md)：空间占用、已实施优化和 GitHub 版本管理方式。
- [实验评价](docs/phase5g_evaluation_2026-09-28.md)：39 例实验协议、评价指标和历史结果。
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

阶段 5G 的运动、感知、跟驰、补位、实时显示和评价链路已经实现。9 月 28 日的一轮完整矩阵记录为 38/39 例形成；据失败例补充了目标槽位被占时的重选规则。修复后的第二轮日志记录到 12 例，当前原始结果目录中没有完整汇总。详细状态见系统说明和检查点。

2026 年 10 月 26 日完成代码职责拆分和存储整理：

- 600 个局部场景及 2/3/4 车道共 1250 拍闭环记录的完整输出摘要，与整理前一致。
- 完整编队回归 150 项、GUI 与审计 91 项、多车道与检测 41 项通过。
- 实际运行三车、15 s 的 SUMO-GUI，完成 151 帧，碰撞和传送为 0。
- 历史结果与临时验证数据采用无损压缩，节省约 4.6 GiB。
- 新轨迹采用紧凑 JSON，字段、数值精度和积分子步完整保留。

## 版本和数据

源码、配置、测试和文档保存在 [32780542/yanjiu1](https://github.com/32780542/yanjiu1)。本地远端 `yanjiu1` 对应这个仓库，目标分支为 `main`；另一个 `origin` 指向历史仓库。

代码版本使用 Git 提交管理。大型轨迹写入被忽略的结果目录，由实验编号与结果摘要索引；历史失败和未完成记录与成功记录一起保留。日常接续先读系统说明，再读检查点末尾，然后定位具体规则函数。
