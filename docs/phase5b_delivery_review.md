# 阶段5B最终交付封存脚本独立审查

2026-09-13。只读审查根目录`tmp/phase5b_save_acceptance.py`；未修改生产source/config、未运行新车辆，也未执行正式交付封存。正式17机制、新run标准重放、比较包和补充包的路径/终态由主任务随后提供，本报告不能替代这些真实包的最终检查。

**修复后未发现本次有界审查范围内未闭合的P1/P2。** 受审最终binder SHA256为`8af823bfe797f87938304f5dfed1100eac556386719925fd2206a87cfb4df25f`。先前确认的三项P2均由主任务修改；本审查仅写入独立tmp夹具和本文档。

|P2|原问题|修复后的要求|独立证据|
|---|---|---|---|
|可选补充变成强制成功前提|无条件要求supplement目录；若competing ON执行失败，原细积分helper无法创建完整记录补充包，合法负结果无法交付|supplement可缺；保留`passed=null/status=not_verified`，按源案例给出`source_case_failed`或`not_supplied`，不计为数值通过|两种缺失原因夹具均正确；提供的数值失败原值仍复制到最终摘要|
|回归日志缺少任务绑定|其他任务只要末行也为276通过且日志哈希自洽，就可被作为当前源码回归|要求精确Python/flags/helper命令、ROOT工作目录、wrapper快照哈希、当前regression helper与source freeze中script SHA相等；首行provenance必须等于source freeze规定投影，末行统计和日志哈希继续核验|错误command/cwd/runner/script/provenance分别拒绝；完整匹配接受|
|标准重放只按数量验覆盖|17份同一个case的通过条目可被算作17案例|17条case名称唯一、与源variants集合一致；每条`source_execution_status`等于原variant status|重复case、未知case、把failed改completed、错误源路径均拒绝；含一项failed的正确17条接受|

原问题的可重放小证据见[旧脚本快照及负探针结果](D:/yanjiu1/keyan1/tmp/phase5b_delivery_probe_20260913T0500/findings.json)。该夹具只构造自封存的极小JSON文件和无关回归命令，直接调用旧binder函数/实际AST检查段，没有伪造或改写正式run。

修复版[18项夹具结果](D:/yanjiu1/keyan1/tmp/phase5b_delivery_fixed_probe_20260913T0525/validation.json)、[受审binder快照](D:/yanjiu1/keyan1/tmp/phase5b_delivery_fixed_probe_20260913T0525/reviewed_script_snapshot.py)、[夹具脚本](D:/yanjiu1/keyan1/tmp/phase5b_delivery_fixed_probe_v2.py)及[直接输入SHA](D:/yanjiu1/keyan1/tmp/phase5b_delivery_fixed_probe_20260913T0525/review_input_hashes.json)已保留。18项使用真实binder的函数或从其main抽取的AST语句块；**不是正式main端到端验收，也不是标准语义、积分或SUMO重放**。正负覆盖还包括未登记文件导致seal拒绝、17次尝试中重复started拒绝、recording失败拒绝，以及保留driving/数值失败和`scientific_accepted=false/phase6_allowed=false`。

## 来源、失败与文档绑定的代码检查

- `sealed`以实际递归文件集合和逐字节哈希与顶层evidence manifest完全相等，拒绝多文件、缺文件和内容变化；当前工作源码重新枚举run.py及既定源码/config目录，必须恰好等于正式run code_hashes和已测试的107文件freeze。输入逐项与正式input_hashes相等。这里不以仅比较文件数量代替源码集合比较。
- 父run evidence manifest与父标准重放validation各有固定SHA；两侧重放都要求成功、无errors/unstarted、来源路径正确、before/after一致、来源manifest等于当前源包，以及上述17名称和失败状态保留条件。
- 正式比较必须是`candidate_parent_new_comparison`，源路径分别是固定父包和当前新包，before/after两次来源manifest均匹配，比较包validation须通过。比较器修复no-trace描述边界后的最终脚本pin已经更新为`948f3e5eadfdfcb5157c951e9d3496494f823009e8298b6ec18e96a5071f9cc4`，与当前helper字节相同；这是证据处理脚本版本绑定，未改控制规则或参数。binder本身不重新计算比较结果；其意义是绑定已由该审查版本产生、封存并核对来源的比较包。
- 若提供补充包，其seal、源路径、来源manifest和原细积分helper脚本pin必须匹配。细积分helper pin仍为`75c13399b78647f8142acde06165ab4b11d36a6b3867e04a1c08f897927d4c2b`。binder保留fine validation原值，未把数值失败强制改成通过；实际create/replay及原误差门槛仍由补充helper执行，本文夹具不能替代它。
- 最终封存仍要求原top.recording_passed=true，并检查expected/started/finalized均为同一17项、无缺失或重复。它不要求top.driving_passed或全队形成通过；原顶层失败字段保存在new_execution_summary，完整run validation另外复制进快照。科学接受和阶段6入口明确为false，不由artifact交付完整推导科学成功。
- 文档列表已加入本文和既有SUMO/本地规则/补充审查、验收、索引、下一入口；已存在的D盘Markdown链接在绑定时核对。实际快照采用源与目标SHA即时相等检查，复制测试freeze、binder、比较/源/标准重放validation、回归result/stdout/stderr/runner，以及存在时的细积分validation/sampling。输出创建全新completion目录并自行封存，不覆盖旧包。

一项审查推断已撤回并明确限制：曾推测“缺trace且标准17案例已通过”的包会被recording门槛不当拦截；继续检查冻结`phase5_r5_replay`后发现，当前版本在case重放后仍无条件读取trace.jsonl等派生记录，真正缺trace不能获得完整17项标准重放通过。因此这不是已确认的第四项P2，未要求修改原标准重放。比较器可描述`failed_before_trace`空前缀，不等于正式标准重放已经支持该缺失证据。若出现不能重建的包，负证据继续保存和报告，但本binder不能把它标为artifact accepted。最终recording门槛已经恢复。

## 操作记录与剩余步骤

|独立日志目录（root/results/operations）|结果|含义|
|---|---|---|
|20260913T043443566348Z_phase5b_delivery_binder_negative_probe_cdd5a2bb|exit0，0.391s|证明旧binder接受重复案例/无关回归，且拒绝缺supplement|
|20260913T043927341892Z_phase5b_delivery_binder_fixed_probe_f81917e5|exit1，0.546s|夹具仍采用已撤回的recording=false应通过假设，被恢复的门槛正确拒绝；该失败原样保留|
|20260913T044010977449Z_phase5b_delivery_binder_fixed_probe_v2_0a088396|exit0，0.375s|按最终门槛执行18项检查，全部符合预期|

v2夹具SHA256为`b1bec4da231580a48fdcba64c19e350689d9a19bfd391ef32cb4035d42bf3059`。回归helper仍为`6211b220da5e27c5a13e20de6ae6e23414fe41d56f733246b7bfca59cfaa60f7`，本次受审freeze SHA256为`f925f7875e74ad7a00e99a1cba2fd6d0bd2f942d5e5640504b8706f79467edfd`。没有因为辅助检查修复而重跑276回归或重启车辆。

剩余步骤由主任务完成：等待已启动固定机制全部终态、执行并核对新标准重放、封存最终比较包、执行适用的活跃保存动作细化及其重放、完成事实文档，再用本版binder实际绑定这些包并核对新completion封存。若上述helper/binder再次改变，本报告的测试结论只归属于已记录SHA，不能直接沿用为新版本通过。
