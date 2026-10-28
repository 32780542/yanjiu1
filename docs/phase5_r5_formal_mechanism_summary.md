# 阶段5：R5新版正式机制包只读配对摘要

2026-09-13（本地时间）。本单元只读已封存的 R5 新版本；没有修改控制器、参数、初态、冻结选择器或旧 A/B/v1 结果，也没有再次运行车辆试验。

**17 个变体的标准语义重放全部通过；实际运行只有 11 个完整执行、6 个失败前缀，没有未启动项。原包 `engineering_passed=false`、`driving_passed=false`、`scientific_passed=null` 原样保留。** 这是八个固定机制案例的 off/on 对照，加首案例的控制半采样；两侧 `formation_enabled=true`，off/on 指 R5 开关。三个竞争案例的两侧各留下 SUMO 碰撞失败，另有前方优先案例的 off 舒适性失败。重放通过证明记录可重建，不证明安全、通行、编队形成或阶段5科学验收通过。

## 来源与可重放证据

正式来源为 [R5运行包](D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/runs/20260912T222655136582Z_203b85c8/validation.json)。来源 evidence manifest SHA256 为 `3bdd28573d5fca50656869b4c745836535a61924b202c88001e4a0fd7c294b76`；代码清单 SHA 为 `fcc7226e0d17fb85ce9f1e56e2b6e2dca1e71544b3e5f4ce253cf3984adaddd7`。本版本来自正式选定的旧 B1 方法加已独立验收的 R5 补全；旧 B1 的开发及 heldout 比较不自动成为此新版的性能证据。

[专用标准重放](D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/replays/20260912T223428312609Z_75c18330/validation.json) 的 SHA256 为 `5c1b748854c825b3bca8b268fb920148fdcd37a6cf7d6a87f111df6ae650a684`，实际读取结果为 `passed=true`、17 cases、`errors=[]`、`unstarted_variants=[]`，来源前后哈希相同。`partial_source_package=false` 表示封存包完整，包内仍有六个执行失败前缀。标准重放重建了动作、私有记忆链、物理前缀、捕获的 SUMO 报告及派生结果；外层摘要本身没有再次执行这些模型。

独立的 [绑定记录](D:/yanjiu1/keyan1/results/phase5/r5_formal_binding_20260912T2250/binding.json) 将上述标准重放、来源清单、两个摘要和逐车表的 SHA 关联起来，检查前后来源相同、17/11/6 范围一致以及原失败字段未变。绑定脚本以独立快照保存，拒绝覆盖已有输出。

| 产物 | 主产物与异工作目录快照重放 | summary SHA256 |
|---|---|---|
| R5机制及0.01s运动摘要 | [主摘要](D:/yanjiu1/keyan1/results/phase5/r5_summary_formal_20260912T2235/summary.json)；[异cwd重放](D:/yanjiu1/keyan1/results/phase5/r5_summary_formal_replay_20260912T2237/summary.json) | `34c08f617944d91b02b29e5c58189372f335a456ac8123c2282dd824b7b20ab6` |
| 独立0.005s附录 | [主摘要](D:/yanjiu1/keyan1/results/phase5/r5_refinement_formal_20260912T2237/summary.json)；[异cwd重放](D:/yanjiu1/keyan1/results/phase5/r5_refinement_formal_replay_20260912T2238/summary.json) | `dd01c8653acbf88738179edae325e45dfc4b6e6775e471c3cef45365b7ee239b` |
| 全量事实与字节核验 | [逐变体和逐车原值](D:/yanjiu1/keyan1/results/phase5/r5_formal_rows_20260912T2241/descriptive_rows.json)；[核验记录](D:/yanjiu1/keyan1/results/phase5/r5_formal_rows_20260912T2241/verification.json) | 核验记录保存各文件完整SHA |

两套主产物均通过 exact file set、逐文件哈希及异cwd快照字节比较，包括 summary、脚本、依赖快照和证据引用。机制分析脚本 SHA 为 `09efc4ddafc8573dc7b0c053e164a0891b1d9c3494da6701a8c6958f7f097658`；冻结 motion helper SHA 为 `1cbdab1433ec01f7547f58dfa873eab0355588249ad0df23a1f6d10576d8b6ca`。摘要工具的17项合成边界和独立负探针验收见 [独立审查](D:/yanjiu1/keyan1/docs/phase5_r5_summary_review.md)。本单元未改变它们。

## 计数和时间含义

抽样“请求”包括失败决策中产生的下一记忆；“提交”只推进 completed 记录后的私有随机状态。本包所有实际请求抽样恰好都提交了，总计9次；仍分别保留两个字段，不能把这一相等推广到其他失败包。新 plan 请求/提交与换道完成分别统计：前者是无 plan 到有 plan 的转变，后者列出控制状态机完成和标准模型车道中心变化事件。中心变化也不代表连续时间的无碰撞证明。

BACKOFF/YIELD/UNKNOWN/ELIGIBLE 时长是 completed 决策区间按该次决策 phase 左保持的总时长，不是连续观察的相位真值。phase 可在 active plan 执行期间保留，因此 ELIGIBLE 时长不等于“停车等待时长”，其低于换道速度门槛的观察次数也不全部表示正在尝试启动。抽样到期只是允许重新检查候选、基础 prepare、速度和原守卫；它不是通行或有限时间重试保证。

均速复用冻结 motion 的0.01s样本梯形时间积分；停车时长沿原阈值 `speed <= 1e-6 m/s` 使用左阶梯积分。初末帧去重，实际纵向/横向加速度与 jerk 包含初态和跨记录边界。失败项的 observed window 可包含已积分但未提交的最后区间；全窗口量为 null，不把不同长度前缀当等时长改善比较。相位提交时长不含该未提交区间。失败尾部的可用横向位移也不称作已提交的通行。

`plans_started_after_observed_wait` 仅表示同一 actor 历史上曾提交 blocking 后又启动了 plan，允许跨 clear/新 episode，不能解释成同 episode 退避导致启动。clear 是自身已提交 episode 结束；再入抽样要求 clear 之后确有新的已提交 draw。guard 的拒绝/尝试只统计 guard 非空项，分母0的拒绝率为 null；“已提交的拒绝”指所在决策区间已提交，不是拒绝请求被执行。

## 八个固定案例的配对事实

下表的完成数均为“控制状态机完成/标准模型中心车道变化”。完整逐变体记录含请求与提交的独立计数、驾驶及舒适结果，见 [17行案例表](D:/yanjiu1/keyan1/results/phase5/r5_formal_rows_20260912T2241/case_table.md) 和 [cases.csv](D:/yanjiu1/keyan1/results/phase5/r5_formal_rows_20260912T2241/cases.csv)。

| 固定案例 | R5 off | R5 on | 有限窗口结论 |
|---|---|---|---|
| single_clear | 20s完整；0 draw；t=0.5启动1个plan；完成1/1 | 同上；半控制周期也完整、完成1/1 | 唯一预登记的无竞争全动作相等配对通过；不能外推其他案例 |
| competing | 失败前缀：已提交2.7s/可用物理2.8s；0 draw；两车t=0.5均启动；完成0/0 | 失败前缀4.6/4.7s；两车各1 draw；均t=2.5启动；完成0/0 | 不同本地退避没有解决该竞争，后续仍有SUMO碰撞报告 |
| speed_floor | 30s完整；0 draw；0 plan；完成0/0 | 30s完整；两车各1 draw；0 plan；完成0/0 | 到期后仍受原5m/s启动门槛限制，未观察到重新启动 |
| entered_priority | 20s完整；0 draw/plan；完成0/0 | 20s完整；0 draw/plan；ego提交YIELD共12.2s，t=12.2 clear | 显式已进入优先触发；没有把让行本身算成完成换道 |
| front_priority | 20s完整但驾驶/舒适失败；两车t=0.5启动，完成0/0 | 20s完整且驾驶/舒适通过；left无plan，right在t=0.5启动，完成1/1 | 本例前方/横移/已进入优先有可见效果；不是全队编队形成证明 |
| reentry | 40s完整；0 draw；t=0.5启动；完成1/1 | 40s完整；1 draw；t=2启动；完成1/1；t=7.1 clear | 截至40s没有第二次draw，预声明再入目标未覆盖 |
| same_private_state | 失败前缀2.7/2.8s；两车t=0.5启动；完成0/0 | 同私有初态1/1；各1 draw；两车t=2启动；失败前缀4.2/4.3s；完成0/0 | 同状态对称反例保留，随机退避没有互斥保证 |
| quantized_private_states | 失败前缀2.7/2.8s；两车t=0.5启动；完成0/0 | 不同私有初态1/2；各1 draw；两车t=2启动；失败前缀4.2/4.3s；完成0/0 | 不同退避长度量化到同一行为时刻，仍可能同时启动 |

competing 的首个本地等待为 1.7772472488870688/1.8718904715041507s；仅按到期和行为网格可得的最早时刻均为2.0s，实际新 plan 均在2.5s。same_private_state 的两次等待均为1.3498423627584213s；quantized_private_states 分别为1.3498423627584213/1.3867846012971192s，两例网格最早均为1.5s、实际 plan 均在2.0s。网格结果不包含 guard/prepare 的成功保证，也没有交换或协调释放时间。

speed_floor 的等待为1.3503197593202356/1.4302393706704328s。两车提交 BACKOFF 为1.4/1.5s，ELIGIBLE 为28.6/28.5s；286/285次 ELIGIBLE 观察均低于原5m/s换道门槛。未降低门槛、提高共同目标速度或根据结果更改初态。reentry 的等待为1.0309104223285486s，提交 BACKOFF 1.1s、ELIGIBLE 6.0s；其模型中心变化在6.49s、episode在7.1s结束，但不存在第二抽样事件。

entered_priority 的 on 中记录 `yield_entered` 112次，guard拒绝25/122；front_priority 的 on-left 记录 `yield_visible_front` 8次、`yield_visible_inward_motion` 12次、`yield_entered` 108次，guard拒绝24/129。上述拒绝原因均为 `neighbor_reachable_occupancy`，不是对实际某一邻居碰撞的定位证明。其余发生随机等待的 on 车辆，yield guard 拒绝/尝试分别为 competing 的0/18、0/19，speed_floor 的0/14、0/15，reentry 的0/11，same/quantized 的每车0/14。未发生 guard 的 off 或无竞争项不能视为守卫已经接受了一个并不存在的让行请求。

全部27个受控 actor-variant 行的提交 UNKNOWN 时间均为0；该正式物理矩阵没有覆盖 UNKNOWN 的恢复。已有单元边界测试不替代本次缺失的物理覆盖。原包121次可见竞争者移除导致 gate/draw 变化的非空洞反事实通过，范围是已重建自身记忆下的抽样比较，不是121次安全通行。

## 真实驾驶、运动与失败前缀

六个失败变体均保存 `SynchronizationError: SUMO collision or teleport reported` 及 SUMO 的 `right` 与 `left` 碰撞警告，lane 为 upstream_1、gap=-4、stage=move。三个 off 的 SUMO 警告原生时刻为2.90s；competing-on 为4.80s；same/quantized-on 为4.40s。这些时刻与表中的本模型提交/积分时间分别保留，不强行对齐为同一时钟。

与此同时，17项保存的本模型 geometry collision/outside/envelope 子步计数均为0。这是记录中两个通道的实际差异：模型子步未检出碰撞不能消除 SUMO 已报告的失败。本单元不把差异归因为“碰撞可达过保守”、具体邻居、精度误差或某项舒适约束；没有为该差异增加调参或复跑。

六个失败项的已观测前缀舒适检查均通过，但没有全窗口驾驶成功结论。另一个明确失败是 front_priority-off：虽完成20s记录且没有SUMO警告，驾驶、舒适和tracking检查为 false；left/right 的最大实际 jerk 为467.43010547145064/299.9972940539316 m/s³，停车16.55000000000001/16.320000000000014s。不能因其记录完整或模型碰撞为0就删去这个失败。

所有 R5-on 受控车辆在各自已观测窗口内的停车时长为0。以下均速是每车时间均值，不能比较不同长度失败窗口后声称改进；全量27行还保存实际纵向加速度 min/max、横向加速度最大值、jerk及速度最小值，见 [actors.csv](D:/yanjiu1/keyan1/results/phase5/r5_formal_rows_20260912T2241/actors.csv) 和 [逐车相位/运动表](D:/yanjiu1/keyan1/results/phase5/r5_formal_rows_20260912T2241/actor_table.md)。外生车辆的标准 actor 指标缺省为 null，原始运动轨迹仍在主摘要中。

| 案例/受控车 | off窗口均速 m/s | on窗口均速 m/s | 窗口范围 |
|---|---:|---:|---|
| single_clear/ego | 5.2865123734150945 | 5.2865123734150945 | 完整20s；half为5.28642629378358 |
| competing/left与right | 6.051309674714639 | 5.793307402980722 | 2.8s与4.7s物理前缀，不等窗口 |
| speed_floor/left | 2.6473153113024606 | 2.7456976189506404 | 完整30s |
| speed_floor/right | 2.6473153113024606 | 2.745696344754072 | 完整30s |
| entered_priority/ego | 4.309578831123906 | 3.986962301979772 | 完整20s |
| front_priority/left | 0.890812187154936 | 3.0823284067659205 | 完整20s；off舒适失败 |
| front_priority/right | 0.9048299291799587 | 5.2865123734150945 | 完整20s；off舒适失败 |
| reentry/ego | 5.24317242952966 | 5.243172426735699 | 完整40s |
| same_private_state/left与right | 6.051309674714639 | 5.840559360299472 | 2.8s与4.3s物理前缀，不等窗口 |
| quantized_private_states/left与right | 6.051309674714639 | 5.840559360299472 | 2.8s与4.3s物理前缀，不等窗口 |

## 独立细积分附录及复放命令

默认R5摘要只计算保存的0.01s主积分运动。另用冻结 motion 的原 `refinement_summary` 读取已保存的首案例 on 的0.005s同请求积分；未再次决策、未运行车辆。范围仅 ego/lead 两车、200个区间、20s：最大实际 jerk 分别为2.0000000000000444/0.0 m/s³，按原2+1e-6容差通过。初态及跨记录边界已经计入。这既不是整个17变体矩阵的细积分检查，也不是连续时间 jerk 证明。

同一首案例原包控制周期减半对照保留最大位置差0.006795317257802753m、航向差0.0014094107195192496rad；同请求积分减半 ego 最大位置差1.0536530175053218e-05m、航向差1.2555110459611107e-07rad。原门槛均通过，范围仍只及预登记首例。

全部命令采用登记 Python 3.12、`-I -B -S` 和外部限时日志。机制命令形态为 `python -I -B -S <已封存script_snapshot.py> --run-dir <正式包绝对路径> --output-dir <全新目录>`，从任意cwd运行；细积分使用对应附录 `script_snapshot.py` 同名参数。比较脚本及其原始绝对路径参数保存在 [抽取快照](D:/yanjiu1/keyan1/results/phase5/r5_formal_rows_20260912T2241/script_snapshot.py) 和以下操作日志中。已存在输出拒绝覆盖，重放必须选新目录。

| 操作 | root/results/operations 下的日志目录 | 退出码/秒 |
|---|---|---:|
| 主机制摘要 | 20260912T223612725855Z_phase5_r5_formal_summary_285154c5 | 0 / 6.078 |
| 异cwd机制快照重放 | 20260912T223720347044Z_phase5_r5_formal_summary_replay_bedefde1 | 0 / 6.234 |
| 独立细积分摘要 | 20260912T223720349044Z_phase5_r5_formal_refinement_cad00431 | 0 / 2.093 |
| 异cwd细积分快照重放 | 20260912T223803002343Z_phase5_r5_formal_refinement_replay_1a533d34 | 0 / 1.922 |
| 全文件字节比较与事实抽取 | 20260912T224144837815Z_phase5_r5_formal_extract_verify_97abb86c | 0 / 0.281 |
| 标准重放终态绑定 | 20260912T224751145379Z_phase5_r5_formal_summary_semantic_binding_4758cf83 | 0 / 0.204 |
| 独立专用标准语义重放 | 20260912T223427979958Z_phase5_r5_formal_semantic_replay_3e602177 | 0 / 303.781 |

## 未通过、未覆盖与后续入口

本单元没有参数变化，也没有新增排名、选择分数或显著性解释。仅 single_clear 的预声明普通 off/on 全动作相等成立；不外推其他案例。R5随机等待已实现且可重放、可见优先分支确有触发，但同状态、时间量化和一般竞争仍可能同时启动并失败；随机不是安全证书。减速候选的原守卫接受/拒绝被保留，未接受时不称安全已经证明。

仍需停留在阶段5：六个竞争失败前缀、front_priority-off 舒适失败、速度门槛下未再启动、reentry未第二抽样、UNKNOWN无正式物理覆盖均未关闭；新版尚无支持其全队编队改善/持续稳定/有限时间通行的证据。下一独立入口应先解释现存SUMO与模型几何差异及同时启动失败，再按新版本和预登记规则验证所需修正；不得由本报告自动授权新调参、成功筛种或进入阶段6。旧比较只支持原先实际测试的旧版本。
