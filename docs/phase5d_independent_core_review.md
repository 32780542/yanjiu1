# 阶段5D：核心等待模型独立规格与代码质量审查

审查日期：2026-09-13。生产目录 `D:/yanjiu1/keyan1/variants/phase5d_local_game` 全程只读。对照为 `variants/phase5c_lane_priority`。本审查阅读了根 [AGENTS.md](D:/yanjiu1/keyan1/AGENTS.md)、[实施计划](D:/yanjiu1/keyan1/docs/phase5d_local_game_plan.md)、[独立文献报告](D:/yanjiu1/keyan1/docs/phase5d_independent_literature_notes.md)、冻结等待模块/控制器/27项测试及相关输入、模型、预测依赖；未重新阅读文献原始全文，也未运行车辆正式实验。

**结论：在已登记参数和原控制器支持的输入域内，未发现阻断性规格或核心代码质量缺陷；本次11项独立探针全部通过，允许核心实现进入预登记的固定比较实验。这个结论只验收有限模型的求解、接入和回退，不证明效果改善、真实车辆共同均衡、任意物理状态安全、停止端可认证、低速换道恢复或阶段5科学通过。** 工具链/正式包完整性与347项完整回归由root另行负责；本报告不把他人回归报告冒充本审查运行。

## 1. 审查范围与证据绑定

冻结源码在探针内先校验，成功运行后又重新计算相同SHA256：

|文件|SHA256|
|---|---|
|[noa/waiting_game.py](D:/yanjiu1/keyan1/variants/phase5d_local_game/noa/waiting_game.py)|`f28d3ac3999f578e5015e4a7be70ee07336237d5f1de5f12122378d6880c067c`|
|[noa/controller.py](D:/yanjiu1/keyan1/variants/phase5d_local_game/noa/controller.py)|`2aa41175145f2b7c9ee2e0d371a1715729410fbb4fdcb020de49ebb7ca7a777d`|
|[tests/test_phase5d_waiting_game.py](D:/yanjiu1/keyan1/variants/phase5d_local_game/tests/test_phase5d_waiting_game.py)|`e9d8e2084bec5b3445c692ea5a8e003f1df6ba352198bfb734735724e905deea`|

输入规格绑定：实施计划SHA256 `e4230aa40e9d344d36a6b4751bca38048378762b55df7bf97e3f016c008afe5b`；独立文献报告SHA256 `72cb1a8125670ea26cf20fea170fc5fd30c0cd2e1e923070782795bae0b26560`。

独立探针位于根 [tmp/phase5d_independent_core_probes.py](D:/yanjiu1/keyan1/tmp/phase5d_independent_core_probes.py)，SHA256 `bdecc5e82caa9f83ea88d6e9aad84901a244cbbde1d4fa4abe5cd035cb5765ad`。探针显式向 `sys.path` 加入冻结variant；只复用原5C时代的测试输入构造器，未调用新增27项测试的方法，也未使用生产 `distance_at` 充当物理积分期望值。

成功命令（cwd为根研究目录）：

```text
python -I -B -S scripts/run_logged.py --label phase5d_independent_core_probes --timeout 180 -- python -I -B -S tmp/phase5d_independent_core_probes.py
```

成功日志目录：[20260913T111020045837Z_phase5d_independent_core_probes_f2a6c540](D:/yanjiu1/keyan1/results/operations/20260913T111020045837Z_phase5d_independent_core_probes_f2a6c540/result.json)。实际结果：11 tests，0 failures，0 errors；测试5.797 s、封装6.312 s；returncode=0，archive_status=complete，Windows Job清理确认 active_processes=0。

|成功产物|SHA256|
|---|---|
|[stdout.log](D:/yanjiu1/keyan1/results/operations/20260913T111020045837Z_phase5d_independent_core_probes_f2a6c540/stdout.log)|`60da006b32c6a22e02f930bf78acc2e7f237c6b44a4a73e41620a34ee47ee938`|
|[stderr.log](D:/yanjiu1/keyan1/results/operations/20260913T111020045837Z_phase5d_independent_core_probes_f2a6c540/stderr.log)|`bd36243658d6cc326745ba36643fac7e2f8122438498b0d60caf45e834008fe6`|
|[result.json](D:/yanjiu1/keyan1/results/operations/20260913T111020045837Z_phase5d_independent_core_probes_f2a6c540/result.json)|`65e25e307b52e78483a65938ae98895e7f5fcd0d5f3b2ba9f7e47a4062e75e47`|

首轮失败独立保留于 [20260913T110859020682Z_phase5d_independent_core_probes_bea7bb74](D:/yanjiu1/keyan1/results/operations/20260913T110859020682Z_phase5d_independent_core_probes_bea7bb74/stderr.log)：10项中9项通过，1项ERROR。根因是**审查脚本自身**将形成代码误写成不存在的 `formation/detector.py`，并非生产行为失败。纠正为实际 `noa/formation.py`、`noa/formation_rules.py`、`simulation/formation_clock.py`，另增加旋转观测/资格边界探针后，完整11项复跑通过。旧日志未改写，生产文件未修改；不能将首轮称为全通过。

## 2. 独立数学验证

生产[有限求解器](D:/yanjiu1/keyan1/variants/phase5d_local_game/noa/waiting_game.py:70)的矩阵以ego行为行、peer行为列。minimax先取每行ego最坏代价，再选最小行；其peer输出仅是ego最坏分支的见证。Stackelberg则为每列保留所有ego最小代价行，计算其中最大的peer代价，再选peer最优列，最终选该列真正实现peer最坏BR代价的ego行。两者没有混用各方效用或把双方代价相加。

独立手算使用比实际3×3上限更大的4×4表，以同时制造多个BR、leader并列与不同ego选择。ego动作依次为 `[-0.8,-0.3,0,0.4]`，peer为 `[-0.5,-0.1,0,0.5]`：

```text
J_ego = [[1,3,4,2],     J_peer = [[6,9,2,0],
         [1,0,2,2],               [2,2,5,1],
         [3,0,0,2],               [8,5,7,8],
         [4,2,0,0]]              [0,0,1,5]]
```

各列BR分别为 `{-0.8,-0.3}`、`{-0.3,0}`、`{0,0.4}`、`{0.4}`。悲观peer代价为 `[6,5,7,5]`，两个最优列按较小peer动作选择 `-0.1`。该列ego=0实现peer代价5，ego=-0.3只有2，因此必须输出 `(ego=0, peer=-0.1)`。这专门排除了“总选最小ego动作”冒充悲观响应的错误。ego行最大值为 `[4,2,3,4]`，minimax输出ego=-0.3，其两个最坏peer列按较小动作输出peer=0，结果与双层不同。

此手算结果及完整诊断经两模式、全部24×24行列排列，共1,152次验证一致。另对ego、peer各2×2且每个代价取 `{-1,0,1}` 的全部6,561对矩阵，使用**完整ego响应函数枚举**构造独立预期，对两模式作13,122次检查，模型动作及完整BR集合均吻合。该oracle枚举从peer每种动作到ego动作的所有映射并以逐项支配关系筛选可接受响应，未调用生产solver或复用其BR结果。

全部相同成本的矩阵验证较小ego、较小peer的最终并列规则；`2^-50`的非零差值仍按严格大小处理，没有暗设epsilon。NaN、正负Inf、bool、字符串、None、超大不可转浮点整数均被拒绝；`[-0.0,0.0]`作为重复动作被拒绝。小矩阵穷举不等同对所有浮点输入的形式证明，但对枚举逻辑、悲观方向和多BR规则提供了独立证据。

## 3. 物理矩阵与适用域

120组直路场景覆盖ego速度 `0,0.1,4.9,5,33.2,33.3`、peer速度 `0,0.1,5,33.2,33.3` 与初始纵向偏移 `-20,0,4,20`。独立oracle把速度视为饱和仿射函数，在达到0和33.3 m/s的时刻分段，使用有理数梯形积分；未使用生产位移函数。1,080个矩阵单元的双方代价均与实现一致，涵盖先停后保持、达到速度上限后保持和signed gap方向。另检验三个姿态角 `0.2,-0.2,0.7` rad及非零局部横向速度：世界vx变换、投影半长D、旋转后的初始signed gap与双方代价一致。这些旋转输入只验证代理计算，不意味着任意横滑姿态属于真实简化车辆模型支持域。

默认非fixed参数确为H=5 s、peer动作±0.5/0、gap与speed权重1、effort权重0.05；当前原目标速度5、hard speed cap 33.3、minimum lane-change speed 5均保留。速度与effort归一化分别固定5与0.5。所有25项被检查的依赖/配置逐字节等于5C，包含13个configs JSON及R5、预测、感知、曲线、运动学和形成相关模块。

新层只在当前可见签名恰好唯一、当前assessment具有登记让行理由、R5 blocking、非UNKNOWN且两车世界vx非负时建表。独立探针确认多签名、空签名、陈旧签名和负peer世界vx回fixed；现有27项测试还覆盖全部登记理由和其他资格回退。候选经过原stop-tail、舒适性与硬界，且在正常控制器生成的base域内不超过base；输出只为本车请求。

## 4. 控制器接入与真实守卫

相对5C的controller差分只有导入、显式模式参数校验和原R5阻断等待位置的选择/守卫/诊断接入。[原等待分支](D:/yanjiu1/keyan1/variants/phase5d_local_game/noa/controller.py:302)仍在非紧急且无准备/提交换道的路径中；R5 assessment、准入次序、clear期、UNKNOWN、原随机状态更新、minimum 5、速度端点、plan逻辑和形成规则未被重写。

两模式各6个真实场景（无当前车道前车，以及前车距离20/23/25/28/32 m）调用真实 `verify_candidate`，包装器仅记录调用、不替代结果。传入同一完整control与原参数对象，hold起止横向位置相同，duration=5 s；所有成功守卫实际 `checked_s=5.5`，包括原0.5 s settle。并未只检查H=5的终点，也未只检查参与博弈的peer。

|实际探针实例|模型请求|最终请求|核实的路径|
|---|---:|---:|---|
|Stackelberg，无前车|0|0|模型请求通过原5.5 s守卫，executed=true|
|Stackelberg，前车25 m|约-4.47×10^-8|-0.5|模型守卫拒绝，fixed守卫通过，fallback=model_guard_rejected|
|Stackelberg，前车20 m|约-0.472805|约-0.472805|模型与fixed守卫均拒绝，按5C保留base，executed=false|
|Minimax，前车20 m|-0.5|约-0.472805|模型恰等fixed，只跑原fixed guard；拒绝后保留base|

第三行即使数值上最终base等于先前模型请求，诊断仍明确模型没有获准执行；不能据数值相等记作“均衡动作通过守卫”。模型选值、guard拒绝和实际applied字段均能区分。fixed/default与5C完整NoaDecision（动作、memory、全部diagnostics）在7速度×4前车布置×2模式表示，共56次比较完全相等。

独立测试还验证：R5 OFF、紧急和active plan路径不调用新selector；更换邻车local标签、反转观测顺序不改变完整决策；替换自身rng值不改变新层动作/诊断且不抽新随机数；UNKNOWN不执行模型；速度0、0.01、1、4.999999999、5、33.3时，既有blocking episode不能获得换道plan/prepare。0与33.3端点在原守卫因执行器状态不可观而拒绝，仍与5C一样保留base。0速样例最终base=2 m/s²，此处不能被报告为新策略通过了停止端守卫。

## 5. 信息边界与代码质量

新模块只依赖dataclass物理签名、math、clip与原局部预测函数，不读取文件、仿真器、随机源、通信接口或全局车辆集合。当前peer来自 `control.observation.neighbors` 转换后的完整物理签名；没有 `track_id` 排序、真实车型/身份/意图访问，也不读取其他车辆controller、memory、奖励或planned action。结果中的model peer动作仅进入本车diagnostics，没有动作发送路径。输入与自身memory不被selector修改。

规格中peer是本车模型leader、ego是模型follower，实现与此一致。这属于ego内部的条件双层计算；对方速度目标5、恒加速度动作及共同signed-gap项都是公开代理假设。共享gap项并未改变为集中式组效用优化。模块头和assumptions已明确不是已知意图、安全证书或共同均衡。

模块小且职责明确：参数/有限值校验、排序后的纯矩阵求解、局部物理矩阵、控制器guard接入相互分开。诊断保存原base/fixed、全部成本/BR、模型选择、实际应用、资格原因和guard原因，能避免把fallback当作成功。无须为本次验收调整生产文件。

## 6. 非阻断局限与表述边界

1. **内部selector依赖调用者物理前置条件。** `validate_parameters`并不验证所有继承参数和全部control字段；正常入口 `decide` 先执行原 `_validate`，再由原纵向控制生成硬界内base。直接以base=-100调用selector会因最终“不超过base”操作得到-100候选，超出硬界。本审查把它作为内部API域限制记录，未在合法controller路径发现可达回归。若以后独立公开该API，应把已校验control/base的前置条件写入接口或额外验证；本轮不为超出范围的直接调用改变冻结源码。

2. **有限数值不等于物理支持域。** 代理允许观测到超cap的peer vx并在预测中夹到33.3；原守卫本身也以原hard bounds/speed assumptions为条件。因此不能从数值有限推出任何现实邻车都被包络覆盖。非零横滑、错误尺寸/时戳、未建模执行器状态等仍需遵守原模型输入约束。控制器直接拒绝NaN输入和非正邻车尺寸的探针已通过；这不构成通用传感故障处理证明。

3. **排序动力学与执行动力学不同。** 5 s代理采用立即生效的世界纵向恒加速度；实际模型含lag、jerk、转向与曲线跟踪。偏差允许存在，原whole-hold guard才决定是否接受新请求。原guard不能认证时，回base是原5C策略，不能写成“fallback也已安全认证”。

4. **精确浮点并列与代理有效性。** exact comparisons按登记实现；非常接近的数值不被当作BR并列。极大但有限输入可能产生溢出并报ValueError，未承诺所有有限幅值均可计算。收益函数、三动作最坏情况和单peer资格都不代表真实对手的全行为空间，端点gap不约束中途安全。

5. **本审查不能代替正式结果。** 尚未在本审查中运行新的SUMO车辆实验；没有平均速度、换道、形成或安全改善结论。未以未运行实验推断模型行动多样性、普遍公平性或低速入口已解决。可使用的结论是：“冻结实现满足已登记的有限局部等待选择及原守卫回退规格，并通过上述独立核心探针。”

审查完成时未修改生产文件，全部报告/探针均留在根docs/tmp与独立操作日志。后续若源码哈希改变，本文工程验收结论不自动覆盖新版本。
