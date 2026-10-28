# 阶段5原规格、实际实现与证据矩阵

本版先在2026-09-12 22:32 UTC核对开发与已落盘子case，随后补入正式R5整包终态及专用标准重放。**旧A/B纵向子集的R5缺项仍是其历史限制；独立新R5版本已经实现并完成控制、案例、记录及整合回归审查，17个正式机制变体已全部尝试并封存，17个案例的标准重放通过且保留6个执行失败前缀。阶段5科学条件未通过，阶段6不放行。** 实现补齐不能抹去旧实验失败，回归/记录通过也不能替代形成、保持和恢复条件。

旧矩阵已原字节归档为[历史版本](/D:/yanjiu1/keyan1/results/phase5/traceability_history_20260912T222831176368Z/phase5_requirement_traceability.md)，SHA256 `9b0ae7c8c1f9bc7680d873a3557af5bf5cc861f728b5842b0e535c0dc250f522`。本次只更新本矩阵，未修改五个冻结输入、源码、配置、主验收或检查点，没有重跑前置/车辆实验。初版未读取heldout性能；最终在两包绑定和冻结配对摘要完成后，按明确授权核对六seed原值及均值/中位数，未据结果重选B。初始状态核对保存在[事实快照](/D:/yanjiu1/keyan1/tmp/phase5_traceability_update_20260913/verified_facts.json)，最终heldout核对见[独立算术与绑定核验](/D:/yanjiu1/keyan1/tmp/phase5_traceability_update_20260913/heldout_final_v1/verification.json)。归档/初始核查日志为`222831006789Z_phase5_traceability_archive_4985b2fa`、`223225252015Z_phase5_traceability_facts_813dc9cd`；后续每次更新前的原稿也留在本次核验目录。

## 版本与已经结束的工作

| 版本/单元 | 固定来源与证据 | 当前事实及效力范围 |
|---|---|---|
| 旧A cost，94源码+5输入 | [A开发包](/D:/yanjiu1/keyan1/results/phase5/runs/20260912T180218593655Z_1e4080c3/validation.json)；[绑定](/D:/yanjiu1/keyan1/results/phase5/comparison_20260912T191153232875Z_binding_6aec92e0)；[21变体独立重放](/D:/yanjiu1/keyan1/results/phase5/replays/20260912T191157153255Z_5b51d3d5/validation.json) | 21/21完成，engineering=true、科学passed=false，绑定/独立重放已通过。六随机全队形成1/6，局部形成3/6；对应OFF全队0/6、局部2/6。不再是“等待A重放”。 |
| 旧B1同车道前优先，96源码+5输入 | [B1开发包](/D:/yanjiu1/keyan1/variants/phase5_rules_front_first/results/phase5/runs/20260912T185217115718Z_0bbe422c/validation.json)；[绑定](/D:/yanjiu1/keyan1/results/phase5/comparison_20260912T200031670602Z_binding_15a2b3aa)；[重放](/D:/yanjiu1/keyan1/variants/phase5_rules_front_first/results/phase5/replays/20260912T200035024556Z_cd52d411/validation.json) | 21/21完成，engineering=true、科学passed=false，绑定/重放通过；六随机全队1/6、局部3/6。 |
| 旧B2前角优先，96源码+5输入 | [B2开发包](/D:/yanjiu1/keyan1/variants/phase5_rules_corner_first/results/phase5/runs/20260912T185217113215Z_3a3b35df/validation.json)；[绑定](/D:/yanjiu1/keyan1/results/phase5/comparison_20260912T200259973699Z_binding_4446e653)；[重放](/D:/yanjiu1/keyan1/variants/phase5_rules_corner_first/results/phase5/replays/20260912T200303509017Z_e6e6d928/validation.json) | 21/21完成，engineering=true、科学passed=false，绑定/重放通过；六随机全队1/6、局部3/6。 |
| 已冻结的正式B选择 | [selection.json](/D:/yanjiu1/keyan1/results/phase5/comparison_20260912T210839292741Z_selection_652993c7/selection.json)；[选择器独审](/D:/yanjiu1/keyan1/docs/phase5_selector_review.md) | 两B均通过10普通case安全/舒适资格，whole_count均1；六case等权确认覆盖C：B1=0.19854938271604936，B2=0.19407407407407404，按预登记选B1。没有用heldout或后来的R5结果选B，也未调整增益/守卫界。 |
| 旧A heldout | [明确run](/D:/yanjiu1/keyan1/variants/phase5_cost_holdout/results/phase5/runs/20260912T211254802638Z_b9c31d10)；[绑定](/D:/yanjiu1/keyan1/results/phase5/comparison_20260912T221225440029Z_binding_a5fd1653/binding.json)；[13变体标准重放](/D:/yanjiu1/keyan1/variants/phase5_cost_holdout/results/phase5/replays/20260912T221228394230Z_8afb9b96/validation.json) | 13/13完整、绑定/标准重放passed=true；原engineering=true、scientific=false保留。六随机全队0/6、局部2/6。subset的complete_suite=false不解释成崩溃或未完成。 |
| 旧B1 heldout | [明确run](/D:/yanjiu1/keyan1/variants/phase5_rules_front_first_holdout/results/phase5/runs/20260912T211254789627Z_3d1257fa)；[绑定](/D:/yanjiu1/keyan1/results/phase5/comparison_20260912T221045541952Z_binding_26b7acbc/binding.json)；[13变体标准重放](/D:/yanjiu1/keyan1/variants/phase5_rules_front_first_holdout/results/phase5/replays/20260912T221048306395Z_e4fc5f51/validation.json) | 13/13完整、绑定/标准重放passed=true；对应已冻结B1选择，原engineering=true、scientific=false保留。六随机全队0/6、局部2/6。未用heldout重新选B。 |
| 旧A/B1/OFF heldout配对 | [冻结heldout_v1产物](/D:/yanjiu1/keyan1/results/phase5/comparison_20260912T230631758620Z_heldout_47117b4d/heldout.json) | passed=true、errors=[]，六seed、18主单位、full_matrix_observed=true、两方法incomplete=[]。六组完整OFF字节一致后各合并一次；半控制对照不增统计分母。三方法全队均0/6、局部均2/6，确认覆盖C均值B1低于A和OFF，见后文。 |
| 新R5补全版本，106源码 | [整合来源](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/r5_integration_provenance.json)；[控制独审](/D:/yanjiu1/keyan1/docs/phase5_r5_controller_review.md)；[记录独审](/D:/yanjiu1/keyan1/docs/phase5_r5_records_review.md)；[案例独审](/D:/yanjiu1/keyan1/docs/phase5_r5_cases_review.md) | 从已选B1整合17个文件差异，保留其参考规则；新实现不是B3，旧heldout不是其验证集。来源SHA `e5698997b4f81e241d389b380f2e2109414758bad8c8cd56c6be52fcb3286dd6`；控制/记录/案例独审无未关闭P1/P2。 |
| 新版本整合回归与正式初态 | [267项回归日志](/D:/yanjiu1/keyan1/results/operations/20260912T222146217240Z_phase5_r5_integrated_regression_with_historical_inputs_46f566ec/result.json)；[正式初态验收](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/initials/validation.json) | 267项、0 failures/0 errors/0 skipped，195.484s，源码不变。初跑4个缺历史fixture错误保留，按原字节复制7个历史输入后通过，未以复制历史证据重认证前置。正式初态已一次冻结，见下文；不是“尚未抽取”。 |

原始门槛以[规格阶段5](/D:/yanjiu1/keyan1/docs/noa_staggered_formation_research_plan_2026-09-10.md:536)、[§9 R1–R5](/D:/yanjiu1/keyan1/docs/noa_staggered_formation_research_plan_2026-09-10.md:368)和[阶段5入口](/D:/yanjiu1/keyan1/docs/phase5_entry.md)为准。30秒形成再保持10秒是已采用目标；runner的`all_frozen_random_whole_formation`是另行明确的更严格包门槛，不是原规格对任意初态的保证，也不能为了现有结果通过而删改。允许实验失败意味着如实交付实现、测试和失败证据，不意味着M2/科学验收通过。

## 原规格到实际实现、证据与限制

| 条件 | 实际实现与证据入口 | 已验证事实／未通过或未覆盖条件 |
|---|---|---|
| 阶段4及运动学前置 | [阶段4验收](/D:/yanjiu1/keyan1/docs/phase4_completion_acceptance.md)；[本輪前置复核](/D:/yanjiu1/keyan1/docs/phase5_prerequisite_review_20260913.md) | 164项前置测试及普通/采样重放在原登记范围有效。本轮复用固定证据，不把小案例能力外推为任意急刹/切入安全。 |
| gap/2gap与六车几何 | [六车算术](/D:/yanjiu1/keyan1/results/phase5/prerequisites_20260913_20260912T1617539387172Z/geometry_and_environment.json)；[新版本formation](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/formation.py) | 邻道15m、同道30m；4m车身的同道静态净空26m。目标相对当前可见参考生成；离线六车布局没有接入在线槽位/调度。静态净空不证明动态插入安全。 |
| R1：风险优先与退出 | [新formation风险/退出分支](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/formation.py)；[R5控制独审](/D:/yanjiu1/keyan1/docs/phase5_r5_controller_review.md) | 基础机动、可见终止、冷却、横向运动/失参优先；新版本增加R5活跃episode抑制编队增量。危险分支立即去掉增量，不声称所有退出均1秒淡出；旧visibility参考释放/重选成功不等于全队恢复。 |
| R2：有限可见前向参考 | [A原cost](/D:/yanjiu1/keyan1/noa/formation.py)；[最终B1规则](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/formation_rules.py)；[B差异说明](/D:/yanjiu1/keyan1/docs/phase5_ifelse_design.md) | A用数值cost，B是追加对照而非cost等价改写。B1同车道前优先，保持仍合格对象优先；侧/后仅占位/安全，不能成为主参考。近距平局按相对速度，仍并列拒绝，未用ID/类型破局。 |
| R3：小增量与原安全筛选 | [PD/总请求送检](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/formation.py)；[原预测器](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/prediction.py) | 附加限幅0.5m/s²，继续原舒适/硬边界、车身扫掠和道路检查。R5让行以实际最终加速度及同道hold plan复查，拒绝保留原fallback；已提交新plan的请求与送检一致。守卫发生拒绝不证明该动作必危险，也不构成全局安全证明。 |
| R4：先纵向，不强制图案换道 | [最终动作](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/formation.py)；[冻结实施范围](/D:/yanjiu1/keyan1/docs/phase5_implementation_plan.md) | 编队层仅改纵向加速度；转向仍属基础NOA。R5约束尚未启动的候选，不增加主动横向编队软代价，也不中断active plan；未验证自主横向重构图案。 |
| R5：迟滞、冷却及竞争让行/随机退避 | [最终r5.py](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/r5.py)；[NOA候选hook](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/noa/controller.py)；[冻结计划](/D:/yanjiu1/keyan1/docs/phase5_r5_completion_plan.md)；[正式机制摘要](/D:/yanjiu1/keyan1/docs/phase5_r5_formal_mechanism_summary.md) | **旧A/B只有迟滞、冷却、物理关联/失效处理，缺原§9.5显式竞争让行/随机退避；新版本已补齐实现与必要单元。** 已进入/实际向内运动优先于同gap资格、明确可见前者让行、不可判定时私有SplitMix64退避；同episode期限跨YIELD保留，到期不重抽，丢帧/歧义保守UNKNOWN。正式共9次请求draw/9次已提交draw；一般竞争、同状态、量化三例两侧均留SUMO失败，不能称随机化保证安全/通行。27个受控actor-variant的UNKNOWN提交时长全部为0，单元覆盖不能冒充正式物理覆盖。 |
| 低速门槛与不可见意图 | [控制边界独审](/D:/yanjiu1/keyan1/docs/phase5_r5_controller_review.md)；[固定机制矩阵](/D:/yanjiu1/keyan1/docs/phase5_r5_case_matrix.md)；[正式机制摘要](/D:/yanjiu1/keyan1/docs/phase5_r5_formal_mechanism_summary.md) | 低于5m/s仍更新时间，但ELIGIBLE不绕过原速度/prepare/guard门槛。speed_floor-on两车各1次draw，286/285次ELIGIBLE观察低于5m/s、30s内均无新plan；reentry-on在7.1s清除episode，但截至40s无第二draw，预声明再入目标未覆盖。准备意图和初始零横移不可见；正式同状态和量化例均在2s同时启动后失败，保留对称/同时到期失效边界。 |
| 独立队形检测 | [检测器](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/experiments/phase5_detection.py)；[检测说明](/D:/yanjiu1/keyan1/docs/phase5_detector.md) | 至少3车、相邻车道、唯一占位连通、同成员5秒确认及确认后10秒保持由离线检测器计算。在线MAINTAINING、局部成功或未经确认覆盖均不能代替whole-cohort成功。 |
| 3/6/12车形成、保持 | [三方法开发选择包](/D:/yanjiu1/keyan1/results/phase5/comparison_20260912T210839292741Z_selection_652993c7/selection.json)；[冻结heldout](/D:/yanjiu1/keyan1/results/phase5/comparison_20260912T230631758620Z_heldout_47117b4d/heldout.json) | 开发三方法六随机均仅5101全队形成，均1/6；局部均3/6，A对应OFF两个12车也局部形成。heldout中A/B1/OFF全队均0/6、局部均2/6，两个3车seed也未形成。原形成/保持条件未通过，不能据小样本估计一般成功率；新R5小机制case不替代该任务。 |
| 失效、恢复与不恢复反例 | [A/B源包科学条件，见版本表](/D:/yanjiu1/keyan1/results/phase5/comparison_20260912T210839292741Z_selection_652993c7/selection.json) | 三包`disturbance_lost_and_recovered=false`；参考出域释放/重入重选=true，不恢复反例保留=true。A扰动t=20开始，到t=80（扰动后60s）未重新确认并保持10s。**恢复成功的通过证据仍缺，不能将其门槛降为工程通过。** |
| 实际速度扰动传播 | [原配对统计独审](/D:/yanjiu1/keyan1/docs/phase5_analysis_review.md)；[A扰动报告](/D:/yanjiu1/keyan1/docs/phase5_cost_baseline_results.md) | 同开关/同初态的有扰动减无扰动，控制网格峰值与梯形L2/RMS按实际速度计算；空间初始排序比不必是变化参考边的传递率，不能声称全频串稳。失败尾不补齐，无改善/未衰减保留。 |
| 固定参考理论与数值 | [理论](/D:/yanjiu1/keyan1/docs/phase5_theory.md)；[半采样修复独审](/D:/yanjiu1/keyan1/docs/phase5_theory_review.md) | 含0.2s执行器和基础NOA半步反馈；ρ(0.1s)=0.991261841446804，ρ(0.05s)=0.9956272956072867。只支持固定参考/权重、巡航、无饱和、守卫接受且R5未介入的局部模型，不能外推混合切换、变拓扑、串稳或全局恢复。 |
| 关闭等价与冻结时钟 | [最终R5Clock](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/simulation/r5_clock.py)；[独立记录审查](/D:/yanjiu1/keyan1/docs/phase5_r5_records_review.md) | 先冻结所有输入，后独立决策/积分/同步/统一commit。新R5关闭保留同5m/s旧方法动作和非R5记忆语义；新schema不冒充旧格式全字节相同。ID/遍历顺序更换按本车私有状态正确路由，无隐含协商。 |
| 私有初态与可重放失败 | [正式初态](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/initials/validation.json)；[正式专用重放](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/replays/20260912T223428312609Z_75c18330/validation.json) | 正式一次冻结9次普通系统熵+4固定对抗状态，允许相同值、不筛选/重抽。PRNG整数和计时/输出精确比对，source与六必需输入绑定；决策抽样与commit分开，失败/未启动不冒充成功。17案例重放passed=true、errors=[]、unstarted=[]；源工程/驾驶false、科学null保留。 |
| 信息隔离与反事实 | [ControlInput](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/perception/contracts.py)；[R5审计](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/experiments/phase5_r5_audit.py)；[正式专用重放](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/replays/20260912T223428312609Z_75c18330/validation.json) | 先完整重放本车memory链，再重建传感历史并进行登记间隔及最后物理帧的same-own-memory反事实；gate/私有抽样/动作敏感性分列。正式登记反事实与源绑定已随17案例重放通过，不能外推到所有反事实世界的独立闭环运行。 |
| 速度、停车、占路与实际舒适性 | [开发运动汇总](/D:/yanjiu1/keyan1/docs/phase5_motion_summary.md)；[heldout运动汇总](/D:/yanjiu1/keyan1/docs/phase5_heldout_motion_summary.md)；[正式R5机制/运动摘要](/D:/yanjiu1/keyan1/docs/phase5_r5_formal_mechanism_summary.md) | 开发三包各21变体已含.01运动、.005保存命令jerk及raw覆盖；103受控标准条目核对、8外生标准指标null。heldout两包各13变体/87 actor行，标准运动字段相符，174行停车均0、主轨迹实际jerk最大1.4620439211998986m/s³；快照重放字节一致。R5主摘要17变体/27受控行不含raw/C，独立.005仅首例ego/lead；失败全窗口量null。各范围不相互替代。 |

## 在线边界、参数与理论限制

实际信息路径是`WorldFrame → 每车IdealSensor → ControlInput(ego, observation, own memory) → decide → 本车动作/记忆`。传感器从本车坐标裁剪前200/后100/侧±50m，输出可见相对位置、速度、朝向、外形和时间；额外延迟为0，无遮挡/噪声模型。完整世界、隐藏车型、旁车future plan、私有流和外生脚本只用于仿真/审计，不进入策略。仿真键排序是记录和独立计算顺序，不是在线优先权或全局调度。

最终B1由当前可见边界/标线重建本车道路中心，没有SUMO laneID。直行4m车身形成的纵向侧带半宽4.3m；同车道投影重叠否决新旧主参考，侧/后只处理占位/安全。它保留自身历史合格参考、前距/相对速度选择与其余可见格点残差权重，不是只输入车道编号的if/else。实际关联不访问track_id；物理唯一匹配也不是身份保证。

统一目标5m/s是之前已登记的开发设置，不是根据最终B或R5结果修改。阶段4默认20m/s时CTH期望净距为3+1.8×20=39m，与30m中心距离对应的26m净空不同；39m不是硬安全距离，5m/s也不是已证明的唯一安全速度。新R5只增加已公开的7个参数：enabled、前方优势2m、实际向内速度阈值0.05m/s、让行0.5m/s²、退避0.5–2s、稳定清除1s；不改PD、安全/舒适界或5m/s目标。

原守卫的额外邻车横向加速度界仍为0，阶段4严重急刹/切入反例和停车投影下的离散jerk范围仍有效。随机化不能补成新的安全证明。局部谱半径小于1要求固定参考/权重、持续可见、巡航、无限幅/速度投影且原安全层接受；参考常速不同于绝对目标速度时有稳态距离偏差，权重0有位置中性模态。R5介入、active机动、拒绝、切参及变拓扑不在该证明内。

## 正式R5冻结与当前失败事实

正式[完整case文件](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/initials/frozen_cases.json) SHA256为`46cff8d466753a50a45e82675bc1a73eedf6e060e50002b9260a985f24aaaf20`：8case、28物理初态、13本车私有记忆，时长20/30/30/20/20/40/20/20s，开关两側formation始终true；16普通变体加首case半控制，共17。冻结入口独审的旧缺口及零熵RED/GREEN保留在[入口证据](/D:/yanjiu1/keyan1/tmp/phase5_r5_freeze_review_20260913)，正式冻结不接受seed覆盖，拒已有initials或正式runs。

明确运行入口是[新版本run.py](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/run.py)的`phase5-r5 --case-file <上述文件>`，不是root旧A入口。[正式run 20260912T222655136582Z_203b85c8](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/runs/20260912T222655136582Z_203b85c8/validation.json)已结束并封存，evidence manifest SHA256为`3bdd28573d5fca50656869b4c745836535a61924b202c88001e4a0fd7c294b76`。live wrapper [222654796674Z](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/operations/20260912T222654796674Z_phase5_r5_formal_mechanism_suite_595af2b3/result.json)退出0、429.625s表示执行流程结束，不表示驾驶成功。

17变体均attempt，11个execution completed、6个failed、0未启动；`complete_matrix_attempted=true`但`complete_execution=false`。全包recording=true、private accounting=true、source_changed=[]；`r5_nonvacuous_gate_or_draw_changes=121`是runner对gate/私有变化的累计计数，不是121个独立统计样本。无竞争首例完整窗口的OFF/ON实际命令相同=true。工程/驾驶均false，科学字段为null。六个执行失败来自competing、same_private_state、quantized_private_states的OFF/ON；另有front_priority OFF虽execution completed但driving=false，不能把这两类失败混同。逐case机制和运动已由下列绑定摘要呈现。

[正式专用重放](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/replays/20260912T223428312609Z_75c18330/validation.json)的validation SHA256为`5c1b748854c825b3bca8b268fb920148fdcd37a6cf7d6a87f111df6ae650a684`，passed=true、17 cases、errors=[]、unstarted=[]。`partial_source_package=false`说明完整登记矩阵已经封存，不能解释为17案例全部完成物理执行；六个失败前缀及捕获的SUMO报告也按失败语义重建。source_engineering/driving=false、scientific=null原样保留。[重放日志](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/operations/20260912T223427979958Z_phase5_r5_formal_semantic_replay_3e602177)退出0、303.781s只证明该次重放验收完成。

首例控制减半对照通过：max_position_error=0.006795317257802753m、max_heading_error=0.0014094107195192496rad；首例`.005s`保存同命令积分对照也通过。独立[细积分附录](/D:/yanjiu1/keyan1/results/phase5/r5_refinement_formal_20260912T2237/summary.json)读取已保存的ego/lead各200区间、20s，最大实际jerk分别为2.0000000000000444/0.0m/s³，按原2+1e-6容差通过，含初态与跨记录边界。这只是首例同请求积分，不是17变体的细积分检查或连续时间舒适性证明。以下竞争子case事实继续保留：

- [competing OFF](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/runs/20260912T222655136582Z_203b85c8/cases/r5_competing_r5_off/validation.json)：status=failed，recording=true、driving=false，28个已保存物理区间/计划300；无R5 draw，2个已提交新plan。
- [competing ON](/D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/runs/20260912T222655136582Z_203b85c8/cases/r5_competing_r5_on/validation.json)：status=failed，recording=true、driving=false，47个trace/完整物理区间，其中46个clock成功提交；请求draw=2、已提交draw=2、已提交新plan=2、gate blocking=37。
- 两者错误均为`SynchronizationError: SUMO collision or teleport reported`。ON几何报告的`collision_substeps=0`、`outside_substeps=0`、`outside_model_envelope_substeps=0`，且末失败interval保留同步读回。**SUMO碰撞/传送报告与模型插值车身几何检查是不同证据；不能据此声称已证明实际模型矩形相撞，也不能因几何检查为0改写驾驶失败。** OFF/ON失败观察窗不同，不能将存续时长差称为安全改善。

[正式机制报告](/D:/yanjiu1/keyan1/docs/phase5_r5_formal_mechanism_summary.md) SHA256为`8c6d3a27e23e8d199f52aadcc424a3e87fc61e5dba45a859f6f3287caeba95e5`；[来源与标准重放薄绑定](/D:/yanjiu1/keyan1/results/phase5/r5_formal_binding_20260912T2250/binding.json) SHA256为`04898ba7242abf30c7645039f8e8578c0a89b934b08b7418c9015a5a81070f0e`。它关联已有标准重放与描述性产物，不是再次模拟或新安全证明。[主摘要与独立细积分的异cwd字节核验](/D:/yanjiu1/keyan1/results/phase5/r5_formal_rows_20260912T2241/verification.json)通过；[逐车/逐变体原值](/D:/yanjiu1/keyan1/results/phase5/r5_formal_rows_20260912T2241/descriptive_rows.json)保留全部失败与未观察项。已只读核对报告/绑定精确hash、摘要全文件集合与快照字节、17案例范围及源驾驶/几何字段。

正式R5开关对照两侧`formation_enabled=true`，不能称编队开关对照。single_clear的预声明完整全动作相等成立；entered_priority-on有YIELD 12.2s但没有plan；front_priority-on本例完整且驾驶/舒适通过，right完成1次机动，off虽满20s却驾驶/舒适/tracking失败。一般竞争on两车在2.5s同时启动；同状态和量化on均在2s同时启动，随后保留SUMO碰撞报告。所有17项模型geometry的collision/outside/envelope子步计数为0，该通道差异仍须解释，不能由摘要推定原因或删除SUMO失败。

speed_floor-on的到期与28.6/28.5s ELIGIBLE提交时长没有产生新plan；reentry-on只观察到一次draw、一次plan和一次episode清除，没有第二次抽样。27受控actor-variant行UNKNOWN提交时间均为0，正式物理矩阵未覆盖UNKNOWN恢复。phase时间按已提交决策左保持累计，ELIGIBLE可以与active plan共存；历史曾等待后启动的计数不证明同episode等待因果。失败物理前缀可能含末次已积分而未commit区间，全窗口量为null，不能以不同长度均速或存续时间宣称改善。

R5实现完成、该机制确有介入，与正式驾驶失败可以同时成立。原17变体已完整尝试、标准重放及描述性产物已闭合，原科学条件没有因此通过：新增小机制矩阵没有验证新版3/6/12车全队形成、持续保持或扰动后全队恢复；旧A/B形成/恢复未通过事实仍保留。后续入口应先解释已保存的SUMO与模型几何差异、同时启动失败，再以独立新版本和预登记处理必要修正及再入/UNKNOWN缺口；本矩阵不授权调参、筛种、全局补救或进入阶段6。

## 旧A/B1正式heldout的完整结果

固定[heldout.json](/D:/yanjiu1/keyan1/results/phase5/comparison_20260912T230631758620Z_heldout_47117b4d/heldout.json) SHA256为`c4a9d6b11429c69673d26b6bdea7b1f6d8cdaf76db19dd93d8cc00d627f3e326`；包manifest SHA为`0b891a1ad0516b57640f7d155d7a18c6082e64fface7512719a34ea7b40d923a`。[冻结配对汇总日志](/D:/yanjiu1/keyan1/results/operations/20260912T230631571676Z_phase5_formal_heldout_paired_summary_6f25d9ef)退出0、57.859s；`passed=true`只表示登记配对及统计产物通过核验，不表示编队科学通过。

A绑定manifest SHA为`e4ac791697da6a19ca6521e74225bf9b07e5a69e9898fd2ec8881abc0d925579`，其13变体replay validation SHA为`83fb197650611b5806cc2c90e1d72835b2603c4d09309cd33212ec37c415a43f`。B1绑定manifest SHA为`d2712125f8cb8456d2663175ad3d3b9ce5b0e5b8c958e51d10ae07489a3f8278`，其13变体replay validation SHA为`ea5b28b8889ff283cd160074142ff1ad9cc2689431508054b5fd87ed0df63bdd`；明确路径见版本表。两包绑定passed=true、errors=[]、source_before=source_after，均对应冻结选择的实际来源。

固定六seed各45s，A/B1及各自重复OFF初态/模型/守卫/检测器匹配，六组完整OFF轨迹均byte_equal后才合并为18个主方法-种子观测。`full_matrix_observed=true`，A/B未启动或执行失败列表均为空；普通控制及首例半采样共13变体每包，但半采样不增六seed分母。统计单位是seed，不能把18个方法-种子观测、174个actor行或采样帧当独立试验增加显著性。

C按已确认局部组的`[formed,end)`时间区间积分，当多组并存时只取最大组成员比例，再除45s；不回填最初5s、不取成员并集，也不等于raw覆盖。六seed等权结果如下：

| seed | 车辆数 | A的C | B1的C | OFF的C | B1−A末占路长度 m |
|---|---:|---:|---:|---:|---:|
| 6111 | 3 | 0 | 0 | 0 | 0 |
| 6112 | 3 | 0 | 0 | 0 | 0 |
| 6211 | 6 | 0 | 0 | 0 | 5.027686787100606 |
| 6212 | 6 | 0 | 0 | 0 | 0 |
| 6311 | 12 | 0.2222222222222222 | 0.2222222222222222 | 0.2222222222222222 | 0.5107907721015863 |
| 6312 | 12 | 0.09333333333333356 | 0.08000000000000003 | 0.2222222222222222 | 0.04405848759779474 |
| 六seed均值 | — | 0.05259259259259263 | 0.05037037037037037 | 0.07407407407407407 | 0.9304226744666645 |

A/B1/OFF的全队成功均0/6、局部成功均2/6（仅两个12车seed）。B1−A的C平均差为−0.002222222222222255，中位数0，全部差异来自6312的−0.01333333333333353；B1−OFF平均差为−0.0237037037037037，中位数0。B1−A的末占路长度平均差+0.9304226744666645m，中位数+0.02202924379889737m；同一数据中B1−OFF平均为−6.660550667625803m，末占路长度缩短不等于形成确认的队形。连续差值均使用两侧完整45s窗口，本包无缺项；原缺项/失败时的null规则未改变。这些是固定六个初态的描述性事实，没有一般成功率、统计显著性、串稳或总体交通收益的结论，也不因此重选B2。

[heldout运动报告](/D:/yanjiu1/keyan1/docs/phase5_heldout_motion_summary.md)保留逐seed均速、停车与raw U/L，以及各自87 actor标准运动匹配和首例3车`.005`同命令jerk。该报告写作时标准绑定尚在运行，此处以上述已完成绑定补齐其来源状态；不把历史“待绑定”字样解释成现在仍待完成。[A主摘要](/D:/yanjiu1/keyan1/results/phase5/motion_20260912T222756595440Z_0a9d4e9c/summary.json) SHA为`6517c475a6eddfd463cacf9158886b33a3be7d3e9de58035b4229e9ab4945085`，[B1主摘要](/D:/yanjiu1/keyan1/results/phase5/motion_20260912T222756612512Z_431a0b01/summary.json) SHA为`bf4993a46bc0274c549e2a4304ff7f3e21665ec3703c4a06ade000c645403988`，与各自异cwd快照重放一致。全部停车0仅指原1e-6m/s阈值下的保存轨迹，不构成形成/恢复证据；raw U/L也不替代C。旧heldout只支持旧A/B1的已测行为，不能用来验证新增R5版本。

## 最终证据状态与原科学门槛

| 原回填项 | 当前最终状态 |
|---|---|
| H1/H2：heldout来源 | 两明确运行包及13变体标准重放、完整绑定均已完成；路径/hash在版本表及heldout段落保留。 |
| H3：heldout配对和运动 | 冻结heldout_v1、六seed/18主单位、完整OFF合并、均值/中位数、逐seed运动/占路/实际约束已填，所有数值负结果保留。 |
| R1/R2：正式R5运行与重放 | 17attempt、11完成、6执行失败、0未启动；17案例重放passed，捕获SUMO报告、私有链及源驾驶失败保留，源/input前后一致。 |
| R3：正式R5描述性摘要 | 9次请求/提交draw、低速无plan、再入无第二draw、同状态/量化同时启动失败、UNKNOWN正式占用0已填；独立`.005`只限首例ego/lead。 |
| S1：原形成/保持/恢复条件 | 开发六seed每方法仅1次全队成功，heldout A/B1/OFF均0/6；原扰动后全队恢复条件仍false。新R5补齐实现和机制介入证据，却未验证新版3/6/12车全队形成/保持/恢复，且存在正式驾驶失败和再入/UNKNOWN覆盖缺口。**当前科学验收未通过。** 实现与记录/分析通过不替代这些门槛，最终主验收与下一研究入口由root负责。 |

**保持阶段5，不放行阶段6三变二/HDV混行或阶段7/8收益矩阵。** 此限制来自仍未通过/未验证的原科学条件和正式证据缺口，不再把“新R5尚未实现”作为当前原因；历史旧A/B的R5缺项仍必须注明，不能用新代码追认旧结果。
