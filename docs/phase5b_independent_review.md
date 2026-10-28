# 阶段5B局部保守放行：独立实现审查

审查日期：2026-09-13。独立审查对象为 `variants/phase5b_conservative_release`，对照为父正式封存 run `variants/phase5_r5_completed/results/phase5_r5/runs/20260912T222655136582Z_203b85c8`。未使用 Git HEAD 作为来源证明，未改生产源码、配置、测试或既有证据，也未运行车辆积分或 SUMO。

**核心实现结论：未发现 P1/P2。** `advance_backoff` 中的三行变化符合本单元预登记规则；独立新跑 40 项控制器/局部门控测试全部通过。此结论允许进入已授权的固定实验，不代表阶段5科学验收、通行改善或一般安全证明。比较 helper 另发现的一个 P2 边界已由维护者修复，本审查使用原样复现脚本重跑 12 项测试后关闭；当前没有未关闭的 P1/P2。

## 来源和变更范围

依据 [阶段5B计划](D:/yanjiu1/keyan1/docs/phase5b_conservative_release_plan.md) 和 [R5根因诊断](D:/yanjiu1/keyan1/docs/phase5b_r5_diagnosis.md) 审查，重点是原期限法在行为时钟上合并启动、低速入口不能由 ELIGIBLE 越过、clear/再入不能由邻车存在推定等已知边界。

[独立来源核验](D:/yanjiu1/keyan1/tmp/phase5b_independent_review/20260913T042823820199Z/source_audit.json)直接枚举生产源目录并计算 SHA256，核对父 `code_hashes.json`、父 `code_snapshot` 的 106 个文件、`clone_provenance.json` 和新 `phase5b_source_freeze.json`。新源实际共 107 个文件；相对父快照严格只有下列四项变化。旧七个输入逐项一致，完整初态 SHA256 仍为 `46cff8d466753a50a45e82675bc1a73eedf6e060e50002b9260a985f24aaaf20`。新计划副本与根计划逐字节相同，计划 SHA256 为 `cdeb037b71ee07487e6dcbe9d8ac335a85c68130f0db3aba31353d902ac78e35`。

|文件|审查确认的变化|新SHA256|
|---|---|---|
|`noa/r5.py`|在已有 deadline 分支增加三行，到期仍 ambiguous 返回 YIELD/阻断|`3425ab301eaab7aae785159efeb036dc18ff83c5a3c47db7fd65d8c504fe1201`|
|`experiments/phase5_r5.py`|仅向 INPUTS 增加本次计划|`da35128ac9763b5650e171e533064015bc3e328fa743cbcffd53132c49c86be4`|
|`tests/test_phase5_r5_controller.py`|更新五个与旧到期语义冲突的用例|`b99d7cf07a28beea8041d31f5a8725fd87e5529dfbd700ffce0c21bce7f49fb0`|
|`tests/test_phase5b_release.py`|新增九个测试|`1525554d5927edb1694a42cf1265753f0acc09e2593062749e50c2fd21f9ad65`|

新冻结文件自身 SHA256 为 `f925f7875e74ad7a00e99a1cba2fd6d0bd2f942d5e5640504b8706f79467edfd`。[完整差异](D:/yanjiu1/keyan1/tmp/phase5b_independent_review/20260913T042823820199Z/source.diff)保留在独立证据目录。测试后重新计算全部新源和父代码快照哈希，均与运行前一致。本次没有独立重验父包全部外层证据文件或重跑父标准语义重放，不把这项代码/输入核验扩大成整包认证。

## 核心规则和信息边界

- 修改发生在 [advance_backoff](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/noa/r5.py:230)，只读本次已有 assessment 的 `reason` 和已有私有期限判定。不新增抽样、随机来源、通信、隐藏意图、真实 ID 排序、车型真值、全局位置调度或共享槽位。
- 未到期分支仍返回 BACKOFF。到期且当前 ambiguous 时，保持 deadline、私有随机状态、抽样计数和 episode；只改变 phase 为 YIELD，并返回 `blocking=true`、`expired_ambiguous_wait`。该次调用对可见签名的正常更新沿用原关联逻辑，不借此新建私有 episode。
- [既有 episode 推进](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/noa/controller.py:222)、[候选 preview](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/noa/controller.py:262)和[最终选定的允许抽样调用](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/noa/controller.py:300)共用此函数。不是只在候选循环拦截；低速、静止或无动机时的旧 episode 也继续阻断。
- `HARD_YIELD`、UNKNOWN/断帧、稳定 clear、新目标及唯一关联分支都先于新分支；其源码逐字节未变。到期不会撤销 entered/inward/visible-front/occupied-corridor 让行，也不会让 UNKNOWN 复活旧签名。新分支没有把清除确认的第一帧改为可启动。
- 可见本车前方优势在原期限之前仍等待；期限之后只获得原候选资格。原 5 m/s 入口、候选守卫、准备时长和行为时钟均未改。重新 ambiguous 会清掉尚未完成的 prepare；已存在 plan 继续原 active 策略。
- 原让行 hold guard 仍执行；拒绝时保留原纵向回退和 `yield_not_certified`，诊断 blocking 保持 true。不能把诊断 reason 被覆盖理解成新规则失效。formation 对活跃 episode 的 FALLBACK 和零附加增量仍生效。
- 新 YIELD 状态使用已有记忆 schema；既有校验允许它携带已到期 deadline。没有引入只能写出、不能再读入的新相位。

## 五项旧测试的负向目的

逐项对照父测试差异，未删除原必要负向约束：

1. 单次抽样/固定 deadline 的长期检查保留，最终相位从 ELIGIBLE 改为 YIELD，并新增 blocking/reason 断言。
2. 低速到期用例改为可见 ego-front，保留到期后 ELIGIBLE、无 plan、仅一次抽样和原加速行为。该旧用例仍缺少当下超车动机，所以不能单独证明速度门槛；这是原用例已有的隔离局限。本次独立探针补了真实慢前车动机，并以达到 5 m/s 时可进入 PREPARE 的对照排除“仅因为无动机”的解释。
3. guard 拒绝用例改为 ego-front，使新规则下确实能到达原 candidate guard；固定 deadline、仅一次抽样和无 plan 都保留，另明确断言原 reject 被保存为 candidate_guard。
4. 旧“不同期限仍可同格启动”反例改为可见 ego-front 后检查原准备期/行为格；其原 ambiguous 反例并未丢弃，而由新用例使用同一固定状态 1/2 检查持续不准备、不提交。同状态 1/1 也保留，未另搜有利随机状态。
5. 期限/序列化一致性用例保留全部无效记忆拒绝断言；合法 BACKOFF 跨期限后的期望改为新的 YIELD/阻断。

## 实际验证

[独立脚本](D:/yanjiu1/keyan1/tmp/phase5b_independent_review.py)仅存于根 `tmp`，使用 CPython 3.12.9、`-I -B -S`，通过 `scripts/run_logged.py --timeout 120` 执行。日志：[结果](D:/yanjiu1/keyan1/results/operations/20260913T042822575362Z_phase5b_independent_review_38159e46/result.json)、[测试输出](D:/yanjiu1/keyan1/results/operations/20260913T042822575362Z_phase5b_independent_review_38159e46/stderr.log)。wrapper 退出码 0，用时 2.469 s；40 tests、0 failures、0 errors。[独立 verification.json](D:/yanjiu1/keyan1/tmp/phase5b_independent_review/20260913T042823820199Z/verification.json)记录源码前后不变。

40 项为原 R5 25 项、新保守放行 9 项和本审查另写 6 项。新增探针均覆盖 0.1/0.05 s：低速/静止/无动机旧 episode；有动机且 ego-front 时原最低速度仍生效；prepare 后恢复 ambiguous；expired hold 被拒绝的原回退；formation 零增量；将同一记忆送入父/新 `advance_backoff` 做差分，确认新语义以外的 HARD_YIELD、ego-front、clear、抽样和期限分支输出相同。它们是构造的局部输入序列和函数级测试，不能替代连续车辆动力学或实际再入场景。

另只读核对实施方保留的 RED/GREEN：`variants/phase5b_conservative_release/results/operations/20260913T041816571054Z_phase5b_release_red_30eb41fb` 为 9 tests、18 个失败 subtests；`...041922272382Z_phase5b_release_green_b2dd1f3c` 为 9 tests 通过；`...041934338104Z_phase5b_r5_related_green_93092d5f` 为 51 tests 通过。本次没有改回冻结源码来重演历史 RED。根 276 项整合回归日志 `results/operations/20260913T042256145127Z_phase5b_integrated_regression_e8243aa0` 的最终 stdout/stderr 已只读核对：276 tests、0 failures/errors/skips、source_unchanged=true；该整合回归由主任务运行，不列为本审查新跑的 40 项。

## 比较 helper 补审

审查初始 helper SHA256：`adafab3c49b240ae382607aeeb02b09279dbdf7b4380ccc3b9cdcd9f795b6611`。

静态确认其正式模式严格要求四个声明源文件变化、106→107 源文件、旧七输入不变且仅增新计划、固定完整初态 SHA 和八个案例、17 项变体及跨版本参数/初态一致。共同前缀按记录索引配对并验证实际时刻/actor cohort；不补齐尾部，输出各自未比较长度。请求与已提交计数分开；任一方不完整时 full-window delta 为 null。OFF 要求非空共同前缀上的动作、记忆、物理链一致；这一字段不应被宣传为未比较尾部或所有未检查诊断字段也已相同。helper 默认 `semantic_replays_bound=false`、`final_acceptance=false`，仍需要主任务绑定实际标准重放。

**P2 已关闭：new ON 在首条 trace 写出前失败时，旧比较入口不能生成完整描述性报告。** 旧 `build_summary` 已支持 `failed_before_trace`，但旧 `create_report` 第168行仍直接打开 `new/cases/<name>/trace.jsonl`，触发 FileNotFoundError；这使已封存的零物理前缀失败无法表示为空共同前缀和 null 全窗口差值。

[独立最小复现](D:/yanjiu1/keyan1/tmp/phase5b_independent_helper_probe.py)使用合成 17 项元数据，mock 来源核验/summary 以隔离该入口边界，不导入项目/车辆模块。原样重跑 7 项既有 helper fixtures 和 3 项独立 fixtures：9 passed、1 error。失败证据：[boundary_reproduction.json](D:/yanjiu1/keyan1/tmp/phase5b_independent_helper_probe/20260913T043138081677Z/boundary_reproduction.json)，日志：[stderr](D:/yanjiu1/keyan1/results/operations/20260913T043137640494Z_phase5b_helper_independent_boundary_f4d77f09/stderr.log)。已立即通知主任务和 helper 维护者；本审查没有修改 helper。

维护者增加 `read_recorded_trace`，只在路径不存在且 summary 明确为 `failed_before_trace` 时返回空记录，替换两个读取入口；其他缺失 scope 或目录冒充 trace 都拒绝。修复后 helper SHA256 为 `948f3e5eadfdfcb5157c951e9d3496494f823009e8298b6ec18e96a5071f9cc4`。本审查阅读最小补丁，并原样重跑独立脚本：维护者的既有 fixtures 由 7 增至 9，加本审查 3 项，合计 **12 tests、0 failures/errors**，wrapper 退出码 0、0.859 s。[GREEN verification](D:/yanjiu1/keyan1/tmp/phase5b_independent_helper_probe/20260913T043530280347Z/verification.json)、[GREEN日志](D:/yanjiu1/keyan1/results/operations/20260913T043529845906Z_phase5b_helper_independent_boundary_green_c6a6fed2/stderr.log)确认该 ON 的空前缀及 null 差值，OFF 空共同前缀仍拒绝，未制造 trace 或提交时长。此 P2 已关闭；正式比较和绑定须使用修复后的 helper 哈希。

## 结论边界

核心局部实现和信息边界审查通过，生产源码未发现 P1/P2；helper 的已复现 P2 经最小修复与独立 GREEN 关闭，当前没有未关闭的 P1/P2。本次 helper 审查包含源码/依赖相关校验路径和合成 fixtures，没有独立再跑旧包完整自比较或新正式包比较。正式 17 变体、标准语义重放、主动竞争 0.005 s 细化、正式比较/验收绑定仍由主任务完成，本文件不提前认证这些结果。持续 ambiguous 下无限等待/停车是本方案明确允许保留的代价；本审查不推出有限等待、互斥、舒适改善、编队形成或阶段6已可开放。
