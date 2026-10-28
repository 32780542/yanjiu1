# 阶段5 R5竞争让行与私有随机退避补全计划

> 执行者按 test-driven-development、verification-before-completion 和本工作区 AGENTS.md逐单元执行，先留RED再实现、保留失败和快照。当前是供主代理审查的独立新版本设计，尚未提交生产实现。使用 brainstorming 与 writing-plans；本计划路径按本次授权指定。无Git HEAD，不提交或改写旧包。

**目标：** 补齐原规格§9.5、§13阶段5要求的潜在同一空隙竞争中的局部让行，以及近似同时不可判定时保守减速与本车私有随机退避；不能把这一明确实现缺项称为已实现算法的一次实验失败。

**架构：** 在新版本基础NOA的未启动换道候选处增加显式纯函数竞争gate；NOA自身记忆保存私有随机流及退避状态。已执行plan先走原分支，后续编队层仍沿用所选旧方法的参考/PD，仅在R5让行期间禁用增量。新Clock从封存初始私有记忆恢复，每车仍只取得自己的冻结传感输入和自身记忆。

**技术：** 现有Python标准库、不可变dataclass、0.01秒运动学积分、0.1秒控制及既有行为采样、原候选预测器与实际SUMO读回。新增原型在已隔离的 `variants/phase5_r5_common_development` 开发，`tmp/phase5_r5_development`仅存外层辅助资料；正式整合只允许进入新独立 `variants/phase5_r5_completed`，从冻结选择器正式选出的旧版本复制后记录父版本hash。

现有A、B1、B2生产、测试、配置、五输入及结果不修改；v1比较脚本与heldout选择规则不修改。本单元不是B3，不参与B选择。旧开发/heldout结果仅支持其实际测试的旧版本，新R5版本必须单独运行、重放、报告；不能复用旧heldout数值冒充新版结果。

## 1. 已核实接口及选择

[原NOA](/D:/yanjiu1/keyan1/noa/controller.py:167)先算纵向约束，已有plan在190–211行提前返回；新候选在221–249行由可见慢前车/车道终止动机产生、逐候选预测、连续prepare并在behavior_event启动。`PREPARE_LC`执行的仍是当前车道跟踪，旁车看不到其准备状态。新gate只能依据“潜在竞争”，不能假称读到了旁车目标或意图。

推荐把R5字段加入**仅新副本**的 `NoaMemory`。现有[formation._base_memory/合并](/D:/yanjiu1/keyan1/noa/formation.py:134)按 `fields(NoaMemory)`往返，这样私有字段自然穿过编队基线调用，不会在子类剥离时重置。缺省 `r5_enabled=false` 保持旧NOA动作语义；新R5回归与记录显式承认新增记忆schema。相较再包一层decide，候选gate能在plan启动前否决，并且不会在基础候选已通过后偷偷改变实际执行加速度。相较删改观察来阻止换道，显式gate能保留原始输入和完整理由，审计者可直接复算。

新副本的 `tests/test_phase4_controller.py:273`原来精确断言NoaMemory字段集合，新增私有字段必须产生一次预期RED并更新该schema断言；其后AST禁止ID/文件/隐藏信息/在线全局random的守卫保持原样。旧A/B测试不改。R5关闭比较的是同物理配置的动作/原NOA字段语义，新增记录schema不能谎称与旧记录全字节相同。

当前 `verify_candidate` 不支持 `plan=None`：[实际函数](/D:/yanjiu1/keyan1/noa/prediction.py:116)访问plan的起止时间并调用reference_target。让行减速复核沿用现formation的同车道零横移 `QuadraticLaneChange(now,current_center,current_center,noa_lane_change_duration_s,max(v,noa_min_lane_change_speed_mps))`，保留原5秒加settle预测时域、原道路/扫掠/邻车界；不修改预测器接口或放宽界限。

## 2. 允许信息与最小几何判据

gate输入仅为 `ControlInput`、自车候选目标中心/当前重建道路、候选实际纵向请求、只属自车的R5记忆及公开参数。道路中心由已有 `reconstruct` 从可见边界/车道线重建；邻车只读投影外形、相对位置、朝向、实际速度。禁止邻车plan/状态机/目的车道、真实ID、局部track_id优先、类型、全局槽位和协商消息。

先检查以下局部近邻条件，避免把同一开放大空隙中相距很远的车辆一概当竞争者；候选对象限于目标车道及其相邻可见条带：

`abs(dx) <= projected_half_length_ego + projected_half_length_neighbor + 2*body_margin + standstill_gap + abs(dvx)*noa_lane_change_duration_s`。

它只是检测潜在同时占据相近纵向走廊的保守启发式，使用当前可见速度，不是完整邻车未来可达集或安全证明。最终动作仍过原完整预测器。直行4m车辆、相对速度零时初始阈值为7.3m（4m投影半和+0.3m两侧margin+3m既有standstill gap）。

**满足近邻条件的已进入者/可见向内运动者先检查，不要求先通过“同间隙”资格。** 目标条带上下边界由本车当前截面的可见边界/标线经本车位姿转换取得，按已有reconstruct的几何去重规则确定对应中心的相邻两条物理线，不凭真laneID或固定车道宽度猜边界。投影车身穿入目标条带内侧超过原几何容差时为已进入；若仍在条带之外但惯性横向速度朝目标条带且超过独立速度阈值0.05m/s，则为可见向内运动。部分跨线车辆即使同时构成目标占位前界/后界、或与本车纵向投影重叠，也必须走显式yield分支，不能被后续间隙资格筛掉。

仅对尚未进入、无超过阈值向内运动的其余候选再比较可见间隙：用目标条带当前占位车辆的纵向投影扩张原body_margin后求占位闭区间并集，剩余开区间是可见空隙。本车当前纵向投影若与占位相交，显式 `yield_occupied_corridor`；否则取包含本车整个纵向投影的开区间。另一潜在竞争者的整个纵向投影必须也落在该同一开区间，边界接触不视为空隙内。没有可见前/后界的一侧记开放，不生成看不见的车辆或全局间隙编号。尚未进入的竞争者本身不属于目标条带占位集合；已进入者已经在前一分支处理，不会用它自己的占位把它从资格中排除。只观测到开放间隙也可以判为潜在竞争，但不能把开放端当作远处安全保证。

规则按顺序执行：

| 条件 | 本车行为 | 必须记录 |
|---|---|---|
| 本车已有执行plan | 原active plan分支优先，原轨迹继续/制动；不清plan、不瞬时回中 | `active_plan_bypass`及原预测 |
| 可见对方车身已经进入目标条带，且与本车潜在走廊相关 | 抑制本车新plan，让可见已进入者先完成 | 投影边界、目标条带、物理dx/dy、`yield_entered` |
| 对方尚未穿入但惯性横向速度朝目标条带且超过0.05m/s，与近邻走廊相关 | 保守抑制本车新plan，不推断其隐藏计划 | 方向、实际横向速度、`yield_visible_inward_motion` |
| 对方尚未进入且中心比自车明确靠前，`dx > r5_front_margin_m` | 抑制新plan，保守减速 | `yield_visible_front` |
| 自车比所有潜在竞争者明确靠前，且无已进入者 | 允许进入原候选检查/prepare，不保证执行成功 | `ego_visible_front` |
| 近似同时，`abs(dx) <= r5_front_margin_m`；或多车关系不能唯一决出本车优先 | 本地随机退避；等待时抑制新plan并尝试保守减速 | `ambiguous_backoff`、自己抽样/到期信息 |
| 无潜在竞争 | 原NOA候选流程；无随机抽样 | `no_potential_competition` |

“已经进入”依据目标可见条带内部与邻车投影车身的非零穿入；边界接触在几何容差内不当作已进入。对方中心本就在目标车道的实际占位按原间隙/安全约束处理，不能因随机到期抢占。不能把 `vy=0`解释为对方不会准备换道；没有可见运动时仍按潜在几何竞争处理。自己的优先结论也不是强制旁车让行的命令。

向内可见速度分支是物理运动线索，不是进入意图。旁车本车道回中可能产生假阳性，进入初期低于0.05m/s仍有盲窗，双方同一tick启动也可能同时没有线索；这三种边界均列入测试与真实记录。后续运动消退/离开按当前可见几何重新判断，不永久保留缓存竞争体；既有预测器额外邻车横向加速度界仍为0。

冻结前的具体predicate例子：目标可见条带为 `[3.3,6.6]m`，自车中心 `(100,1.65)m`，直行车身4×1.8m，双方纵向速度相同，以下均满足7.3m近邻界。邻车中心 `(105,7.4)` 与 `(95,7.4)` 的下车身边缘为6.5m，分别是可能的前/后占位界；`(100,7.4)`与自车纵向重叠。这三例均必须先返回 `yield_entered`，不运行会排除它们的same-gap资格。直行邻车中心y=7.5m仅触线、不进入；若没有其他优先线索，则继续普通近同时规则。尚在y=8.25m的邻车，测得惯性vy=-0.051m/s应触发向中道的inward，让行优先于same-gap；vy=-0.050与-0.049m/s不触发严格“大于”阈值，但仍可作为零/小横速潜在竞争进入后续规则。测试生成真实运动学状态时用一致的heading得到这些惯性速度，不伪造车身侧向自由度。

## 3. 本车私有随机流与不自我延后的计时

新增NoaMemory字段：`r5_rng_state`（64位整数或关闭时None）、`r5_draw_count`、`r5_phase`（IDLE/YIELD/BACKOFF/ELIGIBLE/UNKNOWN）、`r5_deadline_s`、`r5_episode_signature`、`r5_clear_since_s`、`r5_last_time_s`。signature只存本车目标物理中心、前后可见间隙界的物理签名及潜在竞争者物理签名集合，不存任何车辆标识。连续关联按上一时刻位置/可见速度/外形预测的唯一物理匹配；未唯一匹配不能冒充同一参考，也不能查询消失真值。当前时刻重算所有优先关系。

匹配不复用formation的0.2m/s横速资格，因为R5要处理真实换道者。当前共同运动学硬模型下定义 `A_match=max(abs(min_accel_mps2),max_accel_mps2)+max_speed_mps**2*abs(tan(max_steering_rad))/wheelbase_m` 和 `omega_match=max_speed_mps*abs(tan(max_steering_rad))/wheelbase_m`。对正dt的每对7元签名 `(x,y,vx,vy,heading,length,width)`，两坐标的匀速预测残差分别不超过 `0.5*A_match*dt**2+geometry_tolerance_m`，两惯性速度残差分别不超过 `A_match*dt+2*geometry_tolerance_m/dt`，包角后的heading差不超过 `omega_match*dt+geometry_tolerance_m/max(length,width)`，尺寸差不超过geometry_tolerance_m。dt=0只接受完全相同物理签名，不作时间推进。这些量有明确单位，仅作为本车有限历史关联界，不改变预测器的邻车额外横向加速度界0，也不授予安全可行性。

可见前/后间隙界分别按其角色关联，竞争者集合构造二分匹配；只有覆盖旧/新集合的唯一一对一匹配才称同episode。没有完整匹配或存在多组匹配均为UNKNOWN；物理signature每帧随位置更新，但不能因此触发新的抽样。目标中心或已唯一关联的可见前/后间隙角色明确改变可新建episode；没有潜在竞争连续1秒也可清除。单纯旧车辆消失/多车不能区分，不算新gap，UNKNOWN状态只保守阻止新plan并检查当前可见清除条件，不从缓存外推不可见竞争者的位置或动作。持续UNKNOWN可能阻塞，需要如实记录，不保证有限时间通行。

这里的唯一关联仅表示当前获准物理硬域内的兼容匹配，不是真实身份保证。最高速与硬转向同时取上界会使匹配界较宽，多匹配时必须保守UNKNOWN；不能因希望连续而用ID消歧。大于一个合法控制间隔的丢帧不把该界扩大成长期缓存轨迹，只保留退避锁存、标UNKNOWN并重新检查当前可见清除/新episode条件。UNKNOWN是以上NoaMemory中明确登记的新phase，不只是未说明的诊断字符串。

实验初始化为每个车辆实例**独立抽取一次**64位私有状态并封存到完整initial memory。使用离线系统熵生成；不由ID、列表顺序、车道奇偶、全局槽位或期望赢家算seed，也不强制各车seed不同。元数据actor key只用于把已经封存的自身状态路由回该实例。ID重命名/排序置换时搬移车辆及其自身初始记忆，不重新抽样、不改变自己的随机流。复制初态重放从这些状态恢复，在线decide禁止访问random全局状态、墙钟、文件或系统熵。

纯SplitMix64转换（固定64位掩码及标准整数位运算常数）每次从自身state产生一个64位输出，再用高53位映射 `[0,1)`；抽样输出和draw_count记录在自己的新记忆及诊断。此处不是密码算法或通信。`delay = r5_backoff_min_s + u*(r5_backoff_max_s-r5_backoff_min_s)`，deadline=`ego.time_s+delay`，不得依赖仿真actor键。

算法版本固定为 `splitmix64_high53_v1`，本单元的精确定义为：

```python
mask = (1 << 64) - 1
next_state = (state + 0x9E3779B97F4A7C15) & mask
word = next_state
word = ((word ^ (word >> 30)) * 0xBF58476D1CE4E5B9) & mask
word = ((word ^ (word >> 27)) * 0x94D049BB133111EB) & mask
word ^= word >> 31
u = (word >> 11) / float(1 << 53)
```

state与draw_count必须为真正整数而非bool，state在 `[0,2**64)`、draw_count非负；deadline/自身时间必须有限，不能未来的last_time或非法phase组合。R5启用后缺state直接拒绝，不静默初始化或现场重播种。初态清单会保存整数原值和产生方式，不以整数不同作为统计公平性证明。

一次持续的同间隙潜在竞争为一个episode。第一次进入不可判定状态只抽一次；等待期间deadline不可每tick或每次prepare重新设为now+delay。到期锁存为ELIGIBLE，允许重新走**当前**几何检查、完整安全检查和连续prepare；到期不自动启动，也不忽略已进入者/明确前者。若安全拒绝一直存在，记为 `expired_but_guard_blocked`，保持已到期，不能把风险阻塞误写成反复随机等待。不同私有delay可能落到同一behavior_event，必须允许并保留这个失败边界。

phase表示当前处置，deadline是同episode独立保存的退避锁存。合法组合为：IDLE无episode/deadline；YIELD或UNKNOWN可以保留尚未抽样的None deadline，也可以保留既有未来或已到期deadline；BACKOFF有未来deadline；ELIGIBLE有已到期deadline。已有BACKOFF/ELIGIBLE被entered/front/inward或关联UNKNOWN暂时覆盖时，改当前phase但不丢deadline、不减draw_count；后来回到ambiguous继续使用同一个deadline，过期则立即恢复ELIGIBLE。只在该episode首次ambiguous且deadline=None时抽样。明确新episode或连续clear确认才清deadline，draw_count和PRNG状态终身保留。单tick更新时间允许先读到BACKOFF已到期，再转换为ELIGIBLE，不能因输入处于边界而拒绝合法恢复。

已有episode的时间更新在每次合法输入时执行，早于“自车速度至少5m/s才考虑新换道”的条件；车辆因等待变慢时deadline仍可正常到期。ELIGIBLE且当前没有已进入者/明确前者的优先让行约束、仅自车速度不足时，释放新增让行减速，允许原基础纵向恢复，原换道最低速度和prepare均不改变。该episode尚未消退时继续禁止编队增量，避免编队力改变当前让行/恢复决策；不能把R5更新只放在高于5m/s的候选循环内而导致永久低速等待。

同episode在连续1秒无竞争、目标/可见间隙明确改变或本车机动结束后结束；下一次新竞争再抽样。物理关联歧义时保守阻止新plan，记 `episode_association_unknown`，不靠每帧重抽取延后时钟；取得明确新间隙才能新建episode。丢失观测/时间跳跃不补算稳定时间，重新确认后才能启动候选。这个机制可能保守等待；不能保证有限时间通行或对称必然解除。

初始独立私有状态碰巧相同、不同状态产生近似相同到期、对方在本车到期时尚无可见横移，都需要保留为明确反例。不能筛掉这些状态或挑seed让指定车获胜。

## 4. 候选gate及减速的对接点

新纯函数 `assess_candidate(control, road, candidate, memory, p)`返回几何分类、当前优先关系和物理episode签名，不抽样、不改观察；`advance_backoff(assessment,memory,now,p)`只更新自身随机/计时。NOA按原几何顺序评估候选，gate先于该候选的verify/prepare启动。遍历多个候选时先完成无副作用assessment；有一个无需等待且安全可行的候选就沿原流程选它，不为未选候选消耗随机流。没有可启动候选时，只为按原几何顺序首个不可判定候选提交一次backoff更新，防止候选数量/遍历实现影响抽样数。

如果没有ambiguous候选、只有明确YIELD候选，也为按原顺序首个YIELD候选提交自身phase/episode更新，draw_count不变；不能只记录诊断却漏掉让行状态或formation抑制。已有episode的时钟到期、消退与缺帧处理始终先于新候选循环，在无动机/低速时也更新，且不产生新的候选随机抽样。每tick最多提交一次新的episode抽样，重复纯assessment不能耗流。

被R5阻止时清除**未执行**的prepare计时，target/plan保持未启动；状态为 `R5_YIELD` 或 `R5_BACKOFF`。新版本formation风险分支显式覆盖这些状态及仍未启动但等待消退的抑制标志，使编队正加速度不能抵消让行。不剥离或伪造LocalObservation，也不改他车动作。

让行减速请求为 `a_yield = min(a_base, -r5_yield_deceleration_mps2)`，再经过现有停车末端速度反馈、舒适上下界、硬加速度界和运动模型执行器约束；前车/车道终止/紧急约束仍优先，不能把更强紧急制动裁回舒适值。当前车道跟踪不改为零steering。以最终实际请求和同道零横移hold plan调用原verify_candidate；接受才使用新增减速，拒绝则保留原驾驶纵向fallback、抑制新plan，并记录 `yield_not_certified` 与原拒绝结构。**拒绝后的原fallback不称为安全已经证明**，实际扫掠/碰撞/jerk仍由真实运行和重放检验。

进入ELIGIBLE后若实际速度因等待低于原5m/s换道最小速度，则允许基础纵向恢复速度但不额外放行横向，不调低速度门槛。共同目标速度本身也是5m/s，基础恢复可能只从下方渐近接近5，有限窗口内始终不能再次满足启动门槛；ELIGIBLE仅表示本地计时已到期，绝不保证能重试成功。保留这个阈值阻塞反例，不偷偷提高目标或降低启动门槛。真正新plan启动时使用最终执行加速度通过原候选核验，不能用旧a_base的证书给随后改过的请求背书。已active plan保持原分支及既有预测与制动局限，不插入本计划的后处理减速。

新增参数只属于R5新版本：`r5_enabled=true`；`r5_front_margin_m=2.0`；`r5_visible_inward_speed_mps=0.05`；`r5_yield_deceleration_mps2=0.5`；`r5_backoff_min_s=0.5`；`r5_backoff_max_s=2.0`；`r5_clear_stable_s=1.0`。它们是本次预先声明的初始规则值，不来自成功筛参。候选时间域、prepare、行为周期、投影margin和standstill gap均直接引用原公开参数；不改变既有PD、车型/感知模型、硬舒适/安全参数。准确区分并保持原执行器滞后 `acceleration_lag_s=0.2s` 与NOA规划响应预算 `noa_response_time_s=0.3s`。

## 5. 新Clock、记录与重放的具体接点

新副本 `simulation/r5_clock.py`继承FormationClock，构造函数显式接收 `initial_memories`；校验keys恰等于controlled、启用R5时每车有合法独立记录schema，再调用父构造并用已恢复记忆一次性初始化 `self.memories`。`_initial_memory()`无actor参数的原接口不改，默认占位记忆不会用于第一次tick之前的决策。拒绝缺失初态或用同一个可变memory对象共享多车状态。后续冻结输入/独立决策/一次积分协议原样复用。

新副本runner在写初始metadata时存完整 `initial_memories`、PRNG算法名/版本、种子产生方式及自身状态hash；记录前就完成初始化，不在tick时生种子。新版本replay与counterfactual audit都从metadata构造自己的memory链；不得借用记录中的每帧memory当答案。重放全量比对抽样输出、draw_count、deadline、动作、完整新记忆、子步及SUMO读回。仅ID重命名反事实将已封存自身记忆连同相同物理车辆搬移，隐藏类型/未来计划/范围外世界变化保持自身随机流不变；去除可见竞争者必须在至少一个非零规则案例中改变gate或实际动作，不能全部零动作空洞通过。

原已冻结版本phase5-replay不用于解释新schema。新副本可添加 `experiments/phase5_r5.py`、`phase5_r5_replay.py`及独立入口，父包与新版都保持各自hash和清单。实际整合文件清单由主代理审核后冻结：新增 `noa/r5.py`、`simulation/r5_clock.py`、上述新runner/replay、`tests/test_phase5_r5_controller.py`、`configs/phase5_r5.json`；仅新副本修改 `noa/contracts.py`、`noa/controller.py`、必要formation风险合并处、上述NoaMemory schema测试及run新入口。原预测器、积分器、感知器、旧A/B选择评分均不得更改。已建共同底座 `variants/phase5_r5_common_development`；控制单元负责noa/formation/config/controller tests，主代理负责clock/runner/replay/run入口和记录测试，不交叉编辑同一文件。

主代理已明确的新副本最小记录接法：在 `experiments/phase5.py::run_case`新增可选 `initial_memories`及明确R5 clock/schema选择，metadata先写私有初态，缺省旧调用行为不变；在新副本 `phase5_replay.rebuild_clock`按明确schema恢复私有记忆，供独立R5整包入口复用单case真实积分、检测、actual metrics及重放原语。相应两个文件属于主代理编辑范围。新机制与固定案例覆盖单独验收，不能拿原六随机formation scientific字段充当R5通过。反事实要么从metadata重建自己的canonical历史，要么在全量动作/记忆重放证明后明确使用same-own-memory作单步非干涉检查；未经验证的记录memory不能直接当答案。

## 6. 可独立验收任务和必要测试

- [ ] **单元1：私有随机与状态恢复。** 在 `variants/phase5_r5_common_development/tests/test_phase5_r5_controller.py`先写缺失模块RED。固定两个私有状态，各执行同一输入两次必须完全同decision；JSON往返后后续5次抽样逐位一致；同状态对称双车保持对称的反例必须通过；改ID/输入顺序并搬移自身memory结果不变；全局random、time、文件和ID属性AST守卫拒绝。实现纯整数转换/有限状态后GREEN，保存首次与最终日志。
- [ ] **单元2：可见几何与优先。** 合成同目标空隙的outer-lane双车，覆盖已进入/仅边界接触、部分跨线且自身构成前界/后界/纵向重叠仍显式yield的3例、向内速度0.05两侧及等号、回中假阳性与消退/初启盲窗、明确前者dx=2+epsilon、近同时dx=2、反向dx、侧方零横速但潜在竞争、不同可见间隙、相距超7.3m且相对速零的非竞争、三方矛盾、缺间隙边界及唯一物理关联失败。整体平移、真实ID/局部track_id改名和邻车顺序置换不改decision。隐藏plan不同而允许观测完全相同必须同输出。
- [ ] **单元3：计时与NOA优先。** deadline抽样后100个tick保持不变，drawcount仅增1；到期且guard拒绝不得偷偷重抽；BACKOFF/ELIGIBLE→YIELD或UNKNOWN→ambiguous往返保留原deadline和draw；仅YIELD也存phase但不抽样；clear满1秒再入才增下一次draw。验证缺帧不补稳定时间，prepare未达到0.5秒不能启动，两个不同delay同一behavior_event到期、先到期但邻车尚未横移均按当前输入重算；初速5且退避降到门槛以下后，即使ELIGIBLE也可能有限窗口不能重试，明确区别计时到期、候选资格和真实启动。已active plan不被R5清除或转向归零；紧急与车道终止优先；formation不得抵消yield。
- [ ] **单元4：最终动作守卫。** 新减速接受/拒绝两分支、后车存在时更减速也可能拒绝、零速不可观测拒绝、NOA紧急不裁回舒适、hold plan时域与旧guard相同。新plan证书加速度必须等于实际发出请求。r5关闭动作等于对应旧方法；时钟同刻冻结、顺序置换、一次积分；完整PRNG memory进入第一帧并连续保留。
- [ ] **单元5：新格式整包。** 先使用短夹具做红绿：缺/改initial_memories、改一次draw或deadline、截断失败尾、改动作/子步、换源代码hash均被新replay拒绝；抽样后决策已产生但积分/提交前故障时，保留失败记录中的决策新memory而不伪装已经提交，回放恢复相同故障边界及上一已提交memory；历史独立反事实memory不复用答案；同包脚本快照在异cwd重放。保留旧方法off等价与原禁止ID守卫。
- [ ] **单元6：固定小规模真实案例与报告。** 实际SUMO运行前封存下节完整case/physical initial/private RNG初态、来源hash、固定时长；每例只运行登记设置，失败不补抽seed、不调界重试。检查真实速度、纵横向加速度、0.01/0.005秒jerk、车身扫掠、碰撞/传送、等待和进入记录。独立复审代码、记录与反事实，最终区分实现通过、机制触发、科学效果及失败边界。

所有命令使用登记Python `C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe -I -B -S`，外层 `scripts/run_logged.py --label phase5_r5_<unit> --timeout <明确秒数> -- ...`，在新副本/原型cwd执行。测试文件用unittest，不需网络或新增依赖。初次失败、修复与重放各新目录；冻结后不补改已运行代码。

## 7. 预先限定的小规模实际案例

以下是与六seed形成比较分开的机制案例，不计入旧B选择或旧heldout；全部完整物理初态及私有流在运行前一次生成封存。道路使用现有三车道可见直路/可见终止几何，参数保持同一新版本；不由运行结果挑选路线、赢家或流。初始车身必须通过既有不重叠检查，若达不到运行前条件如实报告，不用碰撞初态制造规则成功。

| 固定案例 | 目的和时长 | 验收事实 |
|---|---|---|
| 无竞争单车候选 | 1受控车+必要可见慢前车，20s | 不抽随机；同私有流r5开/关动作应一致，基础机动门槛不变 |
| 两车近同时向同中道潜在空隙 | 两外道受控车及各自慢前车，受控初速预先设8m/s、共同目标仍5m/s，30s | gate在旁车零横移prepare阶段仍触发；各只读自身随机；检查等待/到期/原guard/prepare/真实新plan链，若仍不能启动也保留，不按结果改初速/种子 |
| 等待后低于启动速度门槛 | 受控初速5m/s、共同目标5m/s，其余规则不改，30s | 明确保留ELIGIBLE但速度从下方渐近接近5而不能新启动的反例，不能解释成计时器仍未到期 |
| 已进入者与明确前者 | 同一物理几何的两组20s案例 | 当前已进入者优先；未进入时超过2m明确前者优先，无需随机；没有车型/ID优先 |
| 退避清除与同车再次进入竞争 | 可见外生车的自身速度/横移脚本构成一次出域/再入事件，40s | 脚本只属该外生车，不能协调受控释放；第一次episode不重复抽样，连续清除1s后新episode抽样并可JSON重放 |
| 对称/采样碰撞边界 | 同私有初态两车，以及不同延迟落同behavior_event的固定小案例，各20s | 不保证破坏对称；保留并发尝试、持续拒绝或实际失败，绝不按ID修复 |

这里的“潜在同空隙”是在线可见几何定义；离线真值只用于命名、审计和记录实际进入，不会反馈成为竞争判据。对称、非合作、不可见意图、额外邻车横向加速度界为0等限制仍在。随机化不能补成全局收敛/安全证明；有规则动作但整队仍未恢复，必须继续保留原科学失败。

## 8. 审查后的明确入口

主代理先审上述接口、几何定义、episode/到期逻辑与新版本来源边界；理论代理独立核对近同时、prepare不可观测及随机独立性。通过设计审查后先在已从A冻结源码复制的common底座做单元1–4 RED/GREEN；此举不把A/B任一方当作正式赢家。记录代理同步建立新副本runner/replay最小显式接口，待冻结选择器正式结果后才把已审查overlay应用到所选方法的新副本。新版本真实case清单及私有初态冻结后才执行单元5–6。当前没有以本计划文字冒充已实现R5，也不把已完成旧版本对比冒充新版本验收。
