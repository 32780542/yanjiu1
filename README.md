# 三车道无通信局部自组织编队研究

> **研究接续入口（2026-09-28）。** 当前算法是 `D:\yanjiu1\keyan1` 的 Phase 5G **2026-09-23 恢复版**：代码基线提交 `0a87512`，`41ddb02` 为 GitHub 发布记录；本 README 更新没有改算法。仓库：[32780542/yanjiu1](https://github.com/32780542/yanjiu1)。本地分支叫 `phase01`，向本仓库推送的远端叫 `yanjiu1`、目标分支叫 `main`；本地 `origin` 仍指向旧仓库 `biyesheji1`。

## 当前结论，先于运行说明

| 问题 | 已核实的状态 |
| --- | --- |
| 研究目标 | 三车道车辆在无 V2V/V2I 通信、无中心调度下，只用各自有限局部观测和私有记忆，形成上、下车道对齐、中间车道后移 15 m 的领航者—跟随者编队。 |
| 最新入口 | 根目录 [`runrun.py`](runrun.py)：默认 12 车、seed 1、目标速度 10 m/s、90 s、显示 GUI。顶部常量可直接修改。 |
| 当前实现 | 已接入同车道前车跟驰、局部头车对齐、直接观察三条车道的四层占位、`if/else` 补位换道和安全回退。 |
| 科学验收 | **阶段五没有通过。** 2026-09-23 的当前版本 12 车演示记录了 2 次编队换道、0 次碰撞，却没有形成整队，也未恢复目标速度。早前固定六车的 30 s 形成加 10 s 保持门槛也未通过。GUI 可以展示局部行为，不能证明形成成功。 |
| 工程状态 | 恢复版已提交到上述 GitHub 仓库；推送前的入口与 Phase5G 专项测试通过。它不代表整个历史工作区的测试或所有科学案例通过。 |
| 后续入口 | 继续诊断整队为何不能形成，先保留失败证据，再改通用局部规则、补测试、做真实案例和固定矩阵验收。阶段 6–8 尚未开放。 |

## 研究范围及阶段进度

项目借鉴参考论文和 MATLAB 改编源码中的交错几何与简单纵向修正思想。当前控制器**没有**全局车辆排序、匈牙利分配、共享槽位或中央协调。当前演示中所有物理参与者都是受控普通车辆，没有障碍车、背景车或脚本慢车。研究对象是**编队形成**；稳定编队后的任务级变换、混行博弈、瓶颈效率和能耗收益不在这版结论范围内。

| 阶段 | 已有工作及界限 |
| --- | --- |
| 0–1 | 建立 SUMO 环境、三车道瓶颈路网、参数登记、输入与证据目录。 |
| 2 | 使用简化运动学、车身几何和连续轨迹；不是高保真车辆动力学。 |
| 3 | 建立有限范围理想观测、每车独立感知、统一物理时钟及重放。范围内状态按当前模型精确给出，未模拟遮挡、噪声、漏检或额外传感延迟。 |
| 4 | 基础 NOA 连续行驶和安全门在登记的小案例门槛内通过；不等于编队形成。 |
| 5、5B–5F | 先后探索基础形成、保守释放、车道优先、局部等待博弈、精确端点和持续时间策略。历史试验保留失败与局限；大量旧文档和结果只在原本地工作区，**不属于此 Git 最小运行闭包**。 |
| 5G 当前版本 | 改成动态发车、无通信的简单局部编队演示；2026-09-23 集成分层跟驰和补位规则，随后按用户要求恢复到当日已打开 SUMO 窗口的版本。代码和演示入口存在，整队形成与正式科学门槛仍未通过。 |

完整研究日志与旧失败证据索引在[阶段五检查点](docs/phase5_checkpoint.md)。它是按时间追加的文件；**以末尾 2026-09-23 两节为当前状态**，此前的“下一步”属于历史截面。当前设计目标见[分层局部编队规格](variants/phase5g_pure_formation/docs/superpowers/specs/2026-09-23-phase5g-layered-local-formation-design.md)，前一版思路见[局部队尾领航—跟随规格](variants/phase5g_pure_formation/docs/superpowers/specs/2026-09-23-phase5g-local-tail-leader-follower-formation-design.md)。规格是目标与验收要求，实际行为以代码和运行证据为准。

## 方法总览：信息怎样流动

```text
固定 seed 的物理发车日程（只在实验层）
  → 每个 0.1 s 时刻冻结已发出车辆的物理状态
  → 每辆车分别获取本车状态、可见道路及有限范围邻车观测
  → 各自计算跟驰、分层补位、安全动作并更新私有记忆
  → 同一拍全部决策结束后统一推进简化运动学状态
  → 写出逐帧轨迹、诊断与失败前缀
  → 独立检测器读取物理真值评价几何、形成与保持
  → 完整且可信的轨迹经过校验后在 SUMO-GUI 播放
```

实验层可以知道完整发车日程、参与者集合和评价真值；这些**不能**进入单车控制决策。`runrun.py` 的动态演示由本项目简化运动学模型离线生成轨迹（子进程使用 `--offline`），随后用 TraCI 将轨迹摆放到 SUMO-GUI 中播放；窗口不是 SUMO 原生跟驰模型在线计算出的轨迹。传感器入口为 [`perception/ideal.py`](variants/phase5g_pure_formation/perception/ideal.py)：观测框相对本车前方 200 m、后方 100 m、横向两侧各 50 m，覆盖物理上的三条车道。每辆车单独维护局部轨迹标签；标签只用于保持对仍可见物体的关联，不用真实车辆 ID 决定优先级。换道规则另外把层级窗口截为自车前后 90 m。窗口内另外两条车道的车辆是**直接从观测读取**，不是通过本车道前车数量间接推测。

### 几何、50 m 组件与 90 m 分层窗口

纵向 `x` 随行驶方向增大；物理车道按横向坐标从小到大为 `0=下`、`1=中`、`2=上`。一个完整层要求上、下车的车头纵向对齐，中车位于上车后方 15 m；同车道相邻层车头间距 30 m。位置容差 2 m，形成时速度差容差 1 m/s。不能整除 3 时设计允许尾层缺车，但最终三车道数量之差不应超过 1；这仍是**待验证目标**。

`50 m` 只用于把纵向相邻的**可见车辆**连成局部头尾组件，辅助选跟驰参考。`90 m` 用于换道的四层窗口；两者不是“全局编队视野”。每辆车以自身几何位置作为相对第 `k` 层的外侧基准（中车道位置加 15 m），直接在三条车道查找 `k-2`、`k-1`、`k`、`k+1` 层。只有目标位置 2 m 内实际可见的车辆才占据该层；跨线、速度差过大或局部层几何不一致时暂停补位。代码见 [`noa/simple_formation.py`](variants/phase5g_pure_formation/noa/simple_formation.py) 的 `connected_tail_neighborhood`、`layered_window`、`choose_layered_fill`。

### 纵向跟驰

同车道有前车时选最近的可见同车道前车，以 `前车 x - 30 m` 为目标。上车道局部头车向配置目标速度（默认 10 m/s）巡航；下车道头车尝试与可见上车道头车对齐，中车道头车跟在可见外侧头车后方 15 m。合适参考不存在时执行局部头车巡航。更换参考时考虑当前误差和 2 m 改善门槛，减少无益切换。已经补位的车保留自己的目标锚点；锚点不可见时放弃旧目标并重新判断。

纵向请求采用 `v_request = v_ref + clip((x_target - x_ego)/5, -2, 2)`，再把 `v_request - v_ego` 限制在 `[-3, 2] m/s²`，由控制器结合道路终点和紧急安全控制。它是当前代码中的简化跟驰律，不应表述为已经证明稳定或最优。实现入口是 `choose_formation_target`、`formation_acceleration` 和 [`noa/controller.py`](variants/phase5g_pure_formation/noa/controller.py) 的 `_simple_execute`。

### 分层补位换道

各车先持续跟驰。候选补位要求窗口中无跨线车辆、速度差不超过 1 m/s、层匹配一致，并且相同候选、参考和窗口连续稳定至少 1 s；紧急安全控制会中断候选。选择次序：

1. `k-1` 层已满：第 `k` 层保持。
2. `k-1`、`k-2` 层都未满：第 `k` 层等待更前层先补。
3. `k-1` 未满且更前层已满或不存在：按第 `k` 层当前物理占位选择唯一补位车辆。

当前 `if/else` 对第 `k` 层单车的选择为：仅上车补下、仅下车补上、仅中车补上；双车时，上+下选上车补中，上+中选中车补下，下+中选中车补上。缺位由**另一个车道的实际可见车辆**判断。被选车先按相邻车道逐步换道；目标隔一条车道时分两次相邻移动。抵达目标车道与纵向位置并连续稳定 1 s 后，按当前几何重新分层，不持久化全局层号，也没有终身一次换道限制。

发起换道时当前速度须至少 5 m/s，目标相邻车道可见车辆与本车的车头中心纵向距离须至少 8 m，并通过当前车身占用及道路检查；执行中的横向计划继续接受预测校验，紧急风险可触发制动。这是**当前代码的安全门和回退**，不是所有交通情形的安全证明。长时运行及三车道收窄处的行为仍待核查。

本车私有记忆只存参考轨迹、补位锚点、期望车道、`FREE/JOINING/STABILIZING/FORMED` 状态、稳定起始时刻及窗口签名；没有全局车位表、其他车辆记忆或未来发车表。

### 发车、离线评价与重放

动态演示用固定 seed、`random.Random` 和 0.1 s 控制步长。首车 `t=0` 出现；后续发车间隔默认随机 2.5–4.0 s 并落到控制时刻，车道在三条物理中心随机选择，初速度默认 8–12 m/s。车到时才加入物理状态和 GUI 回放，未发出的车不会成为邻车观测。`runrun.py` 接受 3–60 车，但“可输入”不等于各数量通过形成验收。运行时长需覆盖最后一辆发车后的 30 s 形成期限和 10 s 保持期。

独立检测器 [`experiments/phase5_detection.py`](variants/phase5g_pure_formation/experiments/phase5_detection.py) 事后读取真值，检查车道数、外侧对齐、中车道 15 m 偏移、同车道 30 m 间距、速度差、道路与碰撞、形成时刻和保持区间；检测结果**不反馈控制器**。原登记固定六车科学门槛是 30 s 内形成、再保持至少 10 s，并有换道、无碰撞、几何和舒适合格、速度恢复。动态 GUI 演示用于观察，不能以“轨迹生成完成”替代正式科学验收。

## 代码结构

| 文件或目录 | 职责 |
| --- | --- |
| [`runrun.py`](runrun.py) | 顶部用户常量、只读 `--check`、直接运行和调试入口。 |
| [`demo/sumo_gui.py`](demo/sumo_gui.py) | 环境与证据校验、启动 GUI、按轨迹通过 TraCI 添加车辆并 `moveToXY` 播放。**算法先在独立进程完成，GUI 后打开。** |
| [`phase5g_schedule.py`](variants/phase5g_pure_formation/experiments/phase5g_schedule.py) / [`phase5g_cases.py`](variants/phase5g_pure_formation/experiments/phase5g_cases.py) | 随机发车、固定及演示案例；只在实验层使用完整发车表。 |
| [`perception/`](variants/phase5g_pure_formation/perception) | 每车有限观测及可见道路。 |
| [`simple_formation.py`](variants/phase5g_pure_formation/noa/simple_formation.py) / [`controller.py`](variants/phase5g_pure_formation/noa/controller.py) | 跟驰目标、三车道直接占位、分层补位、私有状态、安全优先及换道执行。旧 `formation_lane.py` 属于另一条历史策略路径。 |
| [`simulation/phase5g_clock.py`](variants/phase5g_pure_formation/simulation/phase5g_clock.py) / [`formation_clock.py`](variants/phase5g_pure_formation/simulation/formation_clock.py) | 到时激活、统一物理时钟、同拍观测与统一推进。 |
| [`models/`](variants/phase5g_pure_formation/models) / [`safety/`](variants/phase5g_pure_formation/safety) | 简化车辆运动、贝塞尔换道参考、车身几何和安全计算。 |
| [`experiments/phase5g.py`](variants/phase5g_pure_formation/experiments/phase5g.py) / [`phase5g_replay.py`](variants/phase5g_pure_formation/experiments/phase5g_replay.py) | 单次运行、JSONL 轨迹、证据封存、求值及语义重放。 |
| [`variants/.../tests/`](variants/phase5g_pure_formation/tests) / 根 [`tests/`](tests) | 规则、控制器、实验与 GUI 入口测试。 |
| [`docs/phase5_checkpoint.md`](docs/phase5_checkpoint.md) | 按时间追加的研究进度、验收和失败证据。 |

当前 Git 只跟踪演示所需的精确运行闭包和少量文档。原工作区另有大量**未跟踪**历史实验、PDF、脚本及 `results/`，它们没有随此仓库上传。仅凭 GitHub 克隆不能假定旧阶段的完整结果包也存在；本文与检查点提供继续研究所需的状态和边界。

## 本机运行与查看结果

需要 Python 3.12、匹配的 SUMO/SUMO-GUI 和 TraCI。本机此前使用 SUMO 1.27.1；程序按 `SUMO_HOME`、非空 `configs/tools.json`、PATH 查找工具并核对来源。其他电脑需先安装和配置自己的 SUMO。路网 [`bottleneck.net.xml`](scenarios/cai2024/bottleneck.net.xml) 已在 Git 中。

`runrun.py` 顶部“用户配置区”就是演示参数入口，直接改常量即可；普通运行不接受额外命令行参数。当前默认值按用途分组如下：

| 配置常量 | 默认值 | 含义 |
| --- | --- | --- |
| `VEHICLE_COUNT`、`RANDOM_SEED` | `12`、`1` | 车辆数与可重放发车种子。 |
| `TARGET_SPEED_MPS`、`SIMULATION_DURATION_S` | `10.0`、`90.0` | 目标速度和总时长；时长还要覆盖最后发车后的形成与保持期限。 |
| `DEPART_INTERVAL_MIN_S`、`DEPART_INTERVAL_MAX_S`、`INITIAL_SPEED_MIN_MPS`、`INITIAL_SPEED_MAX_MPS` | `2.5/4.0`、`8.0/12.0` | 逐车随机发车间隔和初速度范围。 |
| `SHOW_GUI`、`GUI_DELAY_MS`、`AUTO_ZOOM`、`WAIT_BEFORE_CLOSE` | `True`、`40`、`True`、`True` | 是否播放、播放速度、视野和播放结束等待。 |
| `FORMATION_JOIN_RANGE_M`、`MIDDLE_LANE_OFFSET_M`、`SAME_LANE_GAP_M` | `50`、`15`、`30` | 局部组件边界、中车道后移、同车道层间距。 |
| `POSITION_TOLERANCE_M`、`SPEED_TOLERANCE_MPS`、`STABLE_TIME_S` | `2`、`1`、`1` | 位置、速度和连续稳定判据。 |
| `REFERENCE_SWITCH_GAIN_M`、`MIN_FORMATION_LANE_CHANGE_SPEED_MPS`、`HARD_LANE_CHANGE_GAP_M` | `2`、`5`、`8` | 参考切换改善量、发起换道最低速度与目标车道硬净空。 |

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
python -B runrun.py --check
python -B runrun.py
```

`--check` 仅核对顶部配置、SUMO-GUI、TraCI、路网及 Phase5G 入口；不生成轨迹、不创建演示目录、不打开窗口。普通运行**先**启动独立 Python 进程生成并校验完整轨迹，**之后**才打开 SUMO-GUI，故一段时间内没有窗口符合当前流程。12 车、90 s 的一次已记录运行从启动到窗口出现约 69 s；等待时间会随机器和参数变化。恢复版没有额外“正在生成”提示，不要仅因暂未见窗口反复启动。`SHOW_GUI=False` 只生成并校验轨迹；`WAIT_BEFORE_CLOSE` 控制播放完后是否等 Enter。

新轨迹源在本地 `variants/phase5g_pure_formation/results/phase5g/simple_gui_sources/<run_id>/`，GUI 播放记录在 `results/demo_runs/<run_id>_simple_formation_<token>/`（具体目录以程序打印为准）。源目录下 `case/trace.jsonl` 是逐拍轨迹与诊断，`case/validation.json` 是案例评价，`case/detection.json` 是独立检测，`case/lane_changes.json` 是换道事件，`case/speed_recovery.json` 是速度恢复；外层 `validation.json` 和完成锚用于包封存。阅读时先看外层封存状态，再看 `case/validation.json` 的 `summary.whole_cohort_formation_success`、`summary.formation_lane_changes`、`summary.collision_count`，最后看独立检测与逐帧原因。动态 GUI 案例的 `scientific_passed` 可以是“不适用”；不能把它读成“通过”。**外层生成成功、退出码 0、GUI 播放结束，都不等于 `whole_cohort_formation_success=true`。** 失败、中断或后处理未封存的目录应原样保留，不能作为完整通过案例。

当前恢复版在 2026-09-23 的真实本地记录是 `simple_gui_sources/20260923T092319151715Z_1cdf6a95`：12 车、seed 1、90 s；源案例执行完成，记录 2 次完成的编队换道、0 次碰撞，但 `whole_cohort_formation_success=false`，形成/保持时间为空，`speed_recovered=false`。这说明窗口可观察局部跟驰与换道，**没有形成合格整队**。结果包未上传 GitHub，可在原 D 盘工作区核对。

## 测试、证据和未完成工作

从仓库根目录运行当前入口的专项检查：

```powershell
python -B runrun.py --check
python -B -m unittest discover -s tests -p test_runrun_demo.py
python -B -m unittest discover -s tests -p test_phase5g_tracked_baseline.py
python -I -B -S variants/phase5g_pure_formation/tests/simple_formation_test_launcher.py all
```

2026-09-23 推送前的记录分别为自检通过、84/84、8/8、143/143；2026-09-28 更新本文前再次运行上述四项，结果仍分别为自检通过、84/84、8/8、143/143。后一次 Phase5G 完整日志保存在本地 `results/operations/20260928T124921411356Z_readme-phase5g-special_7d955346`。这些是**对应日期的验证证据**，不是未来环境的保证。带全部旧未跟踪研究文件的宽泛根回归曾在 619 项中有 2 项失败、34 项错误，不能据专项通过声称整个历史工作区回归全绿。长命令按工作区约定用 [`scripts/run_logged.py`](scripts/run_logged.py) 保存独立日志并设置超时，不覆盖旧尝试。

当前版本尚未完成分层规格要求的 3、4、5、6、7、8、12 车与双组件真实集成，也没有完成 3/6/12 × seed 1–5 固定矩阵、留出初态和正式科学验收。早期固定六车运行未达到 30 s 形成加 10 s 保持；2026-09-23 的 12 车 GUI 案例也未形成整队。阶段 6、7、8 不据此启动，不能据此宣称交通效率、通行能力、能耗改善或普遍安全。

## 新聊天窗口如何接续

1. 核对工作目录为 `D:\yanjiu1\keyan1`；先读本文、[检查点末尾](docs/phase5_checkpoint.md)、[当前分层规格](variants/phase5g_pure_formation/docs/superpowers/specs/2026-09-23-phase5g-layered-local-formation-design.md)，再读 `noa/simple_formation.py` 与 `noa/controller.py`。不要把规格目标误记为已经通过的结果。
2. 执行 `git status --short`，保护大量未跟踪的历史资料和旧失败包。先用 `rg` 找必要代码，不递归展开 `results/` 源码快照；只暂存本次明确修改的文件。
3. 修改行为前，先把现象缩成可复现测试。保持本车状态、三车道有限局部观测、私有记忆边界；不能用全局车数、真实 ID 优先级、未来发车、他车决策、隐含通信或离线检测结果补救控制。特别不能用“同车道前车数量”代替另一车道 `k-2` 层的直接观察。
4. 核查动态发车、局部跟驰、分层补位及三车道收窄处的真实表现；保留失败、碰撞、未完成和被拒安全门的原始证据。恢复版的 20 车/200 s 长时“完成锚缺失”尚未确认修复，继续这条线必须重新诊断。
5. 先跑受影响专项测试，再按规格做真实案例、独立检测与精确重放；分别验收工程封存和科学形成。每完成一个可独立验收单元，向检查点追加实现、命令、结果、失败和下一入口。
6. 本 GitHub 仓库的推送目标是远端 `yanjiu1` 的 `main`；本地 `origin` 是另一旧仓库。推送前核对目标，不要意外上传 `results/`、PDF 或未跟踪历史资料。
