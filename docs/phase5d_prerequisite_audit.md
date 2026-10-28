# 阶段5D前置与实际控制接入审计

2026-09-13，独立只读审计。结论：**5C已完成的实现和注册实验交付可以作为5D固定父版本；科学验收仍为false，阶段6仍关闭。** 本审计未运行车辆、控制器、标准语义重放或旧313项整套回归，未修改5C源码、报告、运行包或失败证据。5D的局部Stackelberg机制尚未由本审计实现或验收。

## 可复核前置证据

- 父版本：[phase5c_lane_priority](D:/yanjiu1/keyan1/variants/phase5c_lane_priority)。
- 新核验结果：[verification.json](D:/yanjiu1/keyan1/results/phase5d/prerequisites_20260913T104302456188Z/verification.json)，`passed=true`。
- 新独立日志：[result.json](D:/yanjiu1/keyan1/results/operations/20260913T104302289057Z_phase5d_readonly_parent_prerequisites_402e999b/result.json)，退出0，耗时3.64秒，stderr为空，私有Job清理确认无存活子进程。
- 新只读helper：[phase5d_verify_parent.py](D:/yanjiu1/keyan1/tmp/phase5d_verify_parent.py)，SHA256 `8ec360effeac6164b5e27c0fd28416ec7872e72d5c242bc9e0d8fa35262eeaba`；同字节[script_snapshot.py](D:/yanjiu1/keyan1/results/phase5d/prerequisites_20260913T104302456188Z/script_snapshot.py)已保存。helper只使用标准库读取、哈希和AST符号定位，输出到全新目录。

| 固定包 | 完整清单文件数 | evidence_hashes.json SHA256 |
|---|---:|---|
| root 5C交付 completion_20260913T065251926120Z | 24 | `8a6122c44cafca6150d66c71c3e6b15b76c666742213d4a88b30a9a1560e74ad` |
| 5C原正式run 20260913T061451357664Z_cd3da24b | 339 | `3155cca5eaa634ead59353a6327a244ae70730f1fa4ee18f4f6bd9d75c37ff34` |
| 5C扩展run 20260913T062619294263Z_4126e0fd | 207 | `08e1ab0f619dd404fd048d62c3718838224c55d4fbcbaf14d9939be76ae03f5c` |

逐项核验清单自身哈希、完整文件集合、所有清单文件字节哈希、路径不越界。另按已封存acceptance中的8个source_bindings核验5B父run/replay、5C原run/replay、扩展run/replay、比较摘要及三车过程摘要。验收中的313项回归为0fail/0error/0skip、source_unchanged=true；原17及扩展6项重放证据哈希绑定闭合。这里复用既有结果，不声称本次重新执行了这些检查。

当前源码集合与两run的code_hashes/code_snapshot均完全一致：**110文件**，核验前后未变。原正式与扩展的当前输入、input_hashes、input_snapshot各**10文件**一致。扩展快照名`input_snapshot/frozen_r5_cases.json`对应父目录的`phase5c_extension.json`，SHA256 `a21f8a4782955c4fab47ed91218b51f621f8a4d795b2d307b27f986aca4e682a`；不能拿父目录原8例`frozen_r5_cases.json`来比扩展。全部具体输入映射保存在verification.json。

5C的`implementation_and_registered_experiment_delivery_complete=true`与`semantic_replays_bound=true`不等价于驾驶整包、形成或通行普遍通过。原17有3个OFF失败前缀，扩展6有1个OFF失败前缀，front_priority OFF驾驶失败也保留。继承验收仍是`scientific_accepted=false`、`phase6_allowed=false`。

## 实际输入与执行链

控制边界由[perception/contracts.py:11](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/perception/contracts.py:11)的不可变记录约束：`ControlInput`仅含ego、当前local observation、own memory。本车状态含时间、姿态、纵横速度、偏航率、实际观测纵加速度、转角；邻车只给本车坐标系中的相对位置/速度/朝向、可见几何尺寸、同拍测量时间。道路仅含当前可见边界及标线折线。`track_id`虽然存在于传感记录中，不是策略优先权或身份真值。

[noa/prediction.py:31](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/prediction.py:31)把局部相对测量转换为本车姿态定义的世界物理量，再按完整物理签名固定运算顺序，未使用track_id。该坐标转换不提供外部全局地图。[noa/road.py:34](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/road.py:34)只重建所见直路；观察截断边不能当物理车道终点。

真实控制顺序为`formation.decide → controller.decide → 可选R5 → verify_candidate → 基础动作 → 可选B1纵向增量再次verify_candidate`。游戏求解器只能提出本车动作及明确的条件性响应假设，不能读取邻车控制器、车型标签、已提交plan、其他车辆随机态或已算出的动作。关于对方回应的收益模型不能代替原硬运动界；无通信的多个本地求解器也不能被写成共享领导者、全局互斥或有限时间通行证明。

## 精确推荐接入点

| 现有位置 | 事实与对5D的建议 |
|---|---|
| [controller.py:170](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/controller.py:170)，验证、道路重建、纵向基线 | 新独立game模块应消费相同的`ControlInput`、可见road、参数及本车记忆，保持纯函数；禁止接触仿真truth或实验case标签。 |
| [controller.py:193](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/controller.py:193)，已有plan执行与完成 | 这是已提交本车机动的生命周期。每拍仍以实际剩余扫掠重新验证；游戏不能因重新算出角色而瞬间换plan、撤销他车已占据事实或跳过安全检查。 |
| [controller.py:237](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/controller.py:237)，motivation和[248](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/controller.py:248)候选入口 | 仅在现有候选循环里加game无法处理已经低于5m/s的等待车。若研究等待阶段纵向定位，须在新候选入口前形成独立本车提案，仍保留可见前导/路终点约束、UNKNOWN及原guard，并显式记录启用条件。是否要改变最低速度/时长属于另一项数值设计，不能隐式发生。 |
| [controller.py:259](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/controller.py:259)，候选生成与R5 preview；[270](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/controller.py:270)，候选加速度 | 适合把注册后的局部game结果解释为“目标候选及本车纵向请求”。安全约束最终落在**所选实际加速度**与候选的verify_candidate上。未通过应保留具体失败，不得把博弈最优性当安全证书。 |
| [controller.py:280](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/controller.py:280)，选定后commit；[287](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/controller.py:287)，行为拍提交 | 求解器遍历各目标只能preview；仅实际选择后提交本车记忆。原prepare持续性、行为时钟和活跃plan路径仍应一致，防止按候选遍历次数消耗随机态/时钟。 |
| [controller.py:297](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/controller.py:297)，R5等待纵向提案 | 现有实现将让行请求取为`min(base,-0.5)`后限幅，hold plan通过原guard才应用。新等待策略如在此替换，应清楚区分角色阻断、动作拒绝和实际纵向请求，不能把`yield_not_certified`误当gate解除。 |
| [formation.py:166](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/formation.py:166)，B1风险门；[209](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/formation.py:209)，增量最终守卫 | 现有R5 episode、非CRUISE/FOLLOW、plan、可见lane end、冷却及明显横移都会使B1立即清零。若新增本车game状态而不沿用这些风险信号，必须明确B1是否还能修改game提出的纵向动作，并验证最终合成动作。否则“game指令”与实际执行加速度可能不同。 |
| [noa/contracts.py:12](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/contracts.py:12)、[formation.py:31](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/formation.py:31) | 新记忆字段需为本车可重放状态，兼容NoaMemory/FormationMemory转换及JSON恢复，不塞入邻车私人状态。对方关联继续基于当前可见物理唯一性，失观测后不得维持隐形对方位置。 |

R5几何分支[noa/r5.py:131](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/r5.py:131)先处理已进入、可见内向运动和占据，再处理可见优先关系；`advance_backoff`在[251](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/r5.py:251)维护私有期限与清除条件。`UNKNOWN`在[287](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/r5.py:287)保持阻断；clear稳定期在[261](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/r5.py:261)。如果5D替换的是竞争消歧层，应单独说明哪些规则属于其机制，哪些仍是原占据/失观测约束，不得让旧R5和新game各自强制互相矛盾的选择。

## 原守卫必须保留的含义

[prediction.py:98](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/prediction.py:98)对每辆所见邻车使用原硬纵加速度界、非负/最大速度、实测惯性横速及注册横加速度界构造可达占据。[110](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/prediction.py:110)用实际执行器/jerk/转向模型，在剩余plan时长加0.5s的预测范围内逐物理子步检查完整车身的扫掠和可见道路包络。新5s plan对应5.5s guard；不是只比较中心距离或最终间隙。

`neighbor_reachable_occupancy`可表示硬可达包络潜在相交，也可能由自适应细分未排除的叶节点触发；[safety/geometry.py:28](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/safety/geometry.py:28)在细分深度耗尽时保守返回碰撞可能。因此当前日志不能直接识别“必然碰撞”或“过于保守”的细分类因果。不能因game预测对方会礼让、求解得到一组均衡或本车有车道优先权而缩窄原guard中的邻车包络。

停车端还有独立条件：[prediction.py:115](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/noa/prediction.py:115)在实际`vx==0`且观测`acceleration==0`时拒绝，原因`own_actuator_unobservable_at_stop`。模型[kinematic.py:45](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/models/kinematic.py:45)会在零速把负实际加速度观察为0，内部drive可仍为负值。这个状态歧义不能用复制观察加速度或给速度加epsilon伪装成已知执行器状态。速度上限端同样有不可观测拒绝。

## 最低速度失败：实际原因与可支持结论

注册值[phase4.json:22](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/configs/phase4.json:22)为`noa_min_lane_change_speed_mps=5.0`。R5在低速仍推进已有episode（controller:222），但新换道候选入口controller:248严格要求实际速度达到该值。`max(v,5)`只用于构造参考数据，**不提升车辆实际速度**；`lateral_command`使用实际速度平方和实际模型，不能把参考的speed字段当低速机动可执行的证明。

[bezier.py:19](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/models/bezier.py:19)的横向参考由位移与持续时间决定，峰值横向参考速度`2*|Δy|/T`、分段横加速度幅值`4*|Δy|/T²`，不会因为实际速度降低而自行变慢。实际自行车模型[kinematic.py:55](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/models/kinematic.py:55)具有转角、转角速率、滞后和jerk限制。因此改小最低速度必须同时验证真实跟踪、全车身扫掠及完成条件；不能仅修改入口比较符或把5m/s传给参考。

既有[5C有界通行诊断](D:/yanjiu1/keyan1/docs/phase5c_liveness_diagnosis.md:33)已由封存报告绑定，此次未重算车辆：上方0.5s提交、5.6s完成；下方5.6s实际已约4.98699m/s。已进入的上方仍在近域，`yield_entered`延续至17.1s，clear再稳定1s，到18.1s才清episode，此时下方仅约0.03236m/s。随后真实峰值4.51093456m/s（22.96s），较门槛约低0.489m/s，30s末速3.29532589m/s。未进入候选循环时`candidate_rejections=[]`，不能写成“有候选被game或candidate guard拒绝”。

这条链还包含慢前导与B1：19.1s稳定参考物理上对应本车道2m/s慢前导；20.3s首次实际形成增量；22.9sNOA基础+0.29318165、B1增量−0.35032127，实际合成−0.05713962m/s²。不能把持有参考等同于恢复到换道门槛，也不能从这组观察直接推断删除B1的反事实会成功。

60s三车扩展同样未形成全5或受控3持续群组：priority上方1次完成、下方0次，upper获得稳定reference后483拍增量被原guard拒绝。waiting两外侧车43.0s前锚点越过200m可见界后，各170拍UNKNOWN保守阻断。约7.45e-8m/s的upper上端数值下偏与lower真实低速是不同量级问题；`_comfortable_speed`二分返回下界（controller:80）可另行分析上端可行性，不能替代本例低速恢复实验。

因此5D若只把车道优先替换为局部Stackelberg角色分配，应预期仍可能保留全部低速失败。要研究等待后再启动，须在结果前明确本车动作集合、收益/响应假设、等待纵向策略或低速慢机动的单项变化，保存原失败、UNKNOWN、未完成及无改善。前置完整性通过不构成该新机制已安全有效的证据。

## 审阅源码哈希与定位

以下均为父版本实际源码/配置，已与原正式和扩展code_snapshot逐字节一致；verification.json还记录AST顶层定义起止行。

| 文件 | 主要定位 | SHA256 |
|---|---|---|
| noa/controller.py | 80–98停止速度；101–167纵向；170–320决策 | `7deb810fcce825144d55aa2a8dfcb3e547df79daf2f2e3e38e92d796959e7ac2` |
| noa/r5.py | 131–203可见候选；234–248episode关联；251–313回退状态 | `f88f6a4a6de75fd34b1b0563f91187e4bc50b02142382de8ebc9db53bf7f92b4` |
| noa/formation.py | 124–226组合决策；166风险；209增量守卫 | `a4e5fa709eb48c25cbdf382af08fb9ea0ee52b9a505520d0559a4e276efc1800` |
| noa/contracts.py | 11本车记忆；34恢复；56R5记忆验证 | `104eb68e4995ecd08b413a1c1a06b30cf3ade9d2e5fd7a9518782ec58df8e82e` |
| perception/contracts.py | 11本车状态；24邻车测量；58ControlInput | `4c539fadcd60e07774ee9f1d85a25262621ffe65c39db735920605978000ffa9` |
| noa/prediction.py | 31可见物理体；98可达体；110预测验证 | `701ea9b949a6ef804a983f33dce4ea89e9e70e42cf2579bc46de50ed99bebafd` |
| noa/road.py | 13LocalRoad；34可见路重建 | `cac2bd9c8cbedf5f4c528f40466aada88a6b64616d66ac0eaf032ec1cbf69102` |
| safety/geometry.py | 28扫掠碰撞；91扫掠出界 | `b3e0d1ccd127c91240c209d6d6e1cc9b45a45404e9e53520edcfa275ba4d55b9` |
| models/kinematic.py | 45观察；55导数；68积分 | `75ff70bd73ff01e9456b0c70e6f5605218d34213fc9f8bcbda7e92210ead3a54` |
| models/bezier.py | 8参考数据；19横向曲线 | `64d2019c2ffabb3d1a94fb946232303abd353482c3915a1e0fcd3bc8d91836af` |
| configs/phase4.json | 19时长；22最低速度；27settling | `5659fa79aec1b8a684f3dde23945425c09fc7b89233372790d13f131c923ea97` |
| configs/phase5_r5.json | 29让行减速度名称 | `c828ecd82e6a36b91d5526f42072b969ad772da708cc2fb83b162dd67a99ed95` |
