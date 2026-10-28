# Phase 5C 独立规格与代码审查

审查日期：2026-09-13。结论：**所审实现可接受；未发现 P1/P2 问题。** 此结论限于预登记规则、实现边界与有界验证，正式车辆实验及完整受影响回归由主任务另行验收；不代表形成改善或阶段5科学门槛通过。

## 范围与依据

读取根目录 `AGENTS.md`、`docs/phase5c_lane_priority_plan.md`、`docs/phase5c_priority_design_review.md`。只读比较 `variants/phase5b_conservative_release` 与 `variants/phase5c_lane_priority`，独立检查新 `noa/r5.py`、新两组测试、案例 loader、runner、replay，以及其 controller、road、prediction、私有状态与审计接缝。未改生产源码、未运行 SUMO 或正式车辆试验、未派发其他代理、未重跑前置或完整回归。

新增本报告及 `tmp/phase5c_independent_probe.py`。独立探针使用原受限观测接口，并直接加载父 `r5.py` 做差分；没有用父版本期望值的文字转述代替实际比较。

## 先审规格

| 要求 | 审查结果与实现依据 |
|---|---|
| 仅本车、局部可见物理与自身记忆 | 新辅助函数只消费本车姿态、实测车身和观测道路折线。`measured_bodies` 丢弃 track 标签并按完整物理签名排序；未新增邻车意图、车型真值、真实ID、全局槽位或调度输入。案例名及三个相同私有初态仅用于离线初始化。 |
| 唯一可信车道、末端和全车身 | `r5.py:79` 将所有可见水平线段端点与车身矩形两端作为分段点，并检查端点及每个开区间中点；要求存在物理道路上下包络、唯一 strip、车身严格位于 strip 内、唯一共享可见中心。缺线、内部断口、终止后、跨线和等距均不能凭最近中心或标签补齐。车身横纵半尺寸包含朝向，矩形包络是保守近似。 |
| 原先行关系优先 | `r5.py:173` 的 entered、inward、occupied 顺序与父源码相同，仍在车道比较之前；near、同gap筛选及物理 episode 签名均保持原定义。 |
| lane-first 逐对归约 | `r5.py:122` 先比较可信中心 y，再在同车道使用原严格 2 m 纵向差；`r5.py:182` 对 ego 逐对归约，有可信更高者即让行、全部可信更低才放行、其余 ambiguous。未以含容差的相等关系排序全局赢家。 |
| 新原因确实硬阻断 | `yield_visible_upper_lane` 在 `HARD_YIELD` 中；`advance_backoff` 的硬让行分支在私有到期处理之前。ego 获胜使用准确的 `ego_visible_upper_lane`，诊断未加入旧 episode 匹配签名。 |
| UNKNOWN、期限和安全守卫 | `advance_backoff` 主体与父版本逐字相同。UNKNOWN 不因优先权恢复，未到期自身期限继续生效，到期 ambiguous 不重抽或强放行。controller 源码未改，clear 稳定期、PREPARE 每拍复核、原 candidate/hold guard、最低换道速度、active_plan_bypass 与 B1 风险期间形成抑制均保留。 |
| 缺省 False 等价 | 纯 R5 用 `p.get(..., False)`，非 bool 值被拒绝；关闭路径保留父 dx 分支。直接父模块差分覆盖 assessment、gate、动作、诊断及完整自身记忆。研究参数默认 True，参数域与策略域同时记录。 |
| 场景及数值冻结 | 父生成器文件未变；运行模型参数及两个策略参数域与父比较，唯一新增策略键是 lane-priority bool。原8场景不改，新60 s三受控车加两脚本前导按计划固定，三个自身 SplitMix64 初态均为1，未随机重抽。 |
| 双 schema 与记忆完整绑定 | 原 schema 原样委托父 loader。新 loader 重建完整固定 envelope，校验实际父文件 SHA、当前 generator SHA、模型、物理、完整案例及所有记忆字段；以 canonical JSON digest 区分 bool/int。冻结使用 exclusive create，拒绝覆盖。 |
| runner/replay 标志绑定 | INPUTS 增加计划与原字节父案例。原矩阵仍为17项；新矩阵6项中 waiting 项显式 False，其余默认 True。runner、replay 与半步比较使用一致 spec；replay 重建 expected matrix 并逐域比较 metadata，不能靠修改 index、policy 或自报哈希变更等待基线。 |

没有请求的上方车持续阻挡下方车、局部视野不一致、低速或守卫拒绝仍可能造成无限等待；实现与测试未把这些边界改写为有限通行保证。

## 再审质量与测试

核心新增局限于两个纯辅助函数、开关检查和既有参与者分支；状态机关联及随机机制没有附带改动。新测试包含真实 `decide` 无请求上方后车阻挡、原真实 guard 拒绝、最低速度、deadline/UNKNOWN、形成抑制和已提交 plan 绕过。PREPARE 的单项测试使用明确标注的 guard 接缝，其目的为状态转换；另有真实 guard 测试，未据 mock 宣称可驾驶。

三个旧 records 夹具依赖原并排随机抽样前提，现显式选 `lane_priority=False`。已逐项查看差异：身份/顺序逐链比较、精确私有状态重放拒绝及中断保留抽样而未提交状态的断言仍在；中断测试同时给 runner/replay 的 unit matrix 绑定 False。该修改保持旧测试所测性质，未降低新车道规则的断言。

独立源码清单包含110文件，只有7个预期差异：`noa/r5.py`、`tests/test_phase5c_priority.py`、`experiments/phase5c_cases.py`、`tests/test_phase5c_cases.py`、`experiments/phase5_r5.py`、`experiments/phase5_r5_replay.py`、`tests/test_phase5_r5_records.py`。模型、原案例生成器、控制器、感知、预测、道路及形成层均与父源文件相同。

## 独立执行证据

命令：`python -I -B -S scripts/run_logged.py --label phase5c_independent_probe --timeout 120 -- python -I -B -S tmp/phase5c_independent_probe.py`。

日志目录：`results/operations/20260913T060940960623Z_phase5c_independent_probe_693c8e03`。`result.json` 显示 completed、returncode=0、child_returncode=0、外部运行3.796 s、Windows Job清理确认；完整 stderr 显示 **9 tests / 2.921 s / OK**。

- 280组直接父R5 assessment和gate差分：涵盖缺省/显式False、上下ego、多个peer strip/跨线、纵向边界及速度。
- 30拍父R5与新关闭路径的完整 `decide` 链差分：比较动作、诊断、全部自身记忆。
- 参数与源码范围核验；分段、重复和反向折线及平移不改可信归属。
- 车身内部宽度为0.00001、0.01、0.5 m的可见边界断口均拒绝归属；旋转前角超过可见source边界、车身正好触及横向边界均保守拒绝。
- 15个 lane/x actor组合的225对反对称性与3375个三元组传递性检查，以及未知归属检查。
- 新扩展上方受控车的全部22个初始记忆字段分别篡改并更新自报哈希，全部被 loader 拒绝。

本审查未独立重跑24项新核心测试、旧回归或新harness整套测试，不把主任务的进度消息当作本报告的完整回归通过证据。主任务须保存最终全量回归日志并绑定冻结源码后，才进入预登记车辆试验。

## 审查对象哈希

均为 SHA256；前三处旧 records 参数显式False的最终差异已静态复核。

| 文件 | SHA256 |
|---|---|
| `noa/r5.py` | `f88f6a4a6de75fd34b1b0563f91187e4bc50b02142382de8ebc9db53bf7f92b4` |
| `tests/test_phase5c_priority.py` | `c34640ec3115e0c942197741a8a9ebd850d51b6c35b2d6018280acdaf060cd3f` |
| `experiments/phase5c_cases.py` | `e4bbf8f57c4a7157e9372af8d9295275d6bfd4764513046760239a082da3e461` |
| `tests/test_phase5c_cases.py` | `1c992274ede512c35503ee39f7b18d3bfba6e353293ab95fd4048f09000e606a` |
| `experiments/phase5_r5.py` | `edb35376e6058ac93623342f665f9df140bd3a5bce4f341dd743d1b255acd2c5` |
| `experiments/phase5_r5_replay.py` | `de8211cf573980dfe7fb5d5d6d5a11a4ff868d02467927b69679aae682f0a054` |
| `tests/test_phase5_r5_records.py` | `e6cd5c28e56a0e9141e9c6b8cc74c7d529b722ad26da52e0c0adcdc647b3ad54` |
| 根目录 `tmp/phase5c_independent_probe.py` | `6c2acccd6e55fd1119dcad0f1c114136efb1307890704773e8335baa321a235b` |

接受实现不等于接受科学结论。后续必须保留守卫拒绝、碰撞、低速、原生SUMO失败、未完成及无改善；阶段6仍需独立科学门槛，不能因本次静态偏序及软件测试通过自动开放。
