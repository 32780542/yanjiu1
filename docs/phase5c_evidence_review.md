# 阶段5C证据 helper 独立审查

审查于2026-09-13 06:11 UTC。范围是根目录的只读比较/扩展摘要 helper、回归冻结 helper 与最终 binder；不评价尚未完成的正式车辆实验结果。

**当前范围内没有未关闭的P1/P2。** 三项独立复现的P2已由主任务修改 helper 并经本审查 fresh GREEN 关闭。最终14 tests、0 failures、0 errors；本审查没有修改生产源码、运行车辆、重跑历史实验或修改旧结果。正式17+6项运行、标准语义重放、313项整合回归及最终验收实例仍由主任务另行完成和绑定，不能用这14项数据测试替代。

## 来源与执行证据

已读取根[AGENTS.md](D:/yanjiu1/keyan1/AGENTS.md)、[预登记计划](D:/yanjiu1/keyan1/docs/phase5c_lane_priority_plan.md)、相关原始summary/motion helper、保存格式、原形成检测器及runner/replay必要片段。使用完成前核验技能；所有测试命令由run_logged保存独立日志，120秒外部上限。

|审查对象|最终测试读取的SHA256|
|---|---|
|`tmp/phase5c_compare_priority.py`|`6024f3014166ff069c3253c3e9e3d0841d37971c4b11ba88b72ec72d1e9978f8`|
|`tmp/phase5c_gradual_summary.py`|`a39c273187853f729e68225ac7b02ed338b0ed2bb3f2b3d9dfdde59a4538c445`|
|`tmp/phase5c_regression.py`|`c6178de93830fa4f8c5cf2f9032846f0a0adef9be3c3173b3fe60e766b32f31a`|
|`tmp/phase5c_save_acceptance.py`|`92ec27c1a6c0cd91c3b148ebf0ca48eac8a3e8691b6c6f34b328f20ca4d74738`|
|[独立测试脚本](D:/yanjiu1/keyan1/tmp/phase5c_evidence_review_tests.py)|`671af050b454e98767545b039c699221ed2321a5802a5e91b49f4c6506cde8d3`|

最终命令为CPython 3.12.9的`-I -B -S tmp/phase5c_evidence_review_tests.py`，经`--label phase5c_evidence_review_final_green --timeout 120`包装。wrapper退出码0、1.656秒；unittest运行14项、1.268秒。[wrapper结果](D:/yanjiu1/keyan1/results/operations/20260913T061130497643Z_phase5c_evidence_review_final_green_c7ecb30b/result.json)、[完整测试输出](D:/yanjiu1/keyan1/results/operations/20260913T061130497643Z_phase5c_evidence_review_final_green_c7ecb30b/stderr.log)、[独立verification](D:/yanjiu1/keyan1/tmp/phase5c_evidence_review_tests/20260913T061130820130Z/verification.json)记录测试期间四个helper hash未变。

测试仅加载根helper及无项目依赖的原形成检测器。扩展入口夹具是新建于根tmp的合成、自封存数据包：实际执行hash、矩阵和元数据校验，不mock这些校验；夹具不代表冻结场景或模拟结果。binder回归探针通过AST抽取真实main中的只读regression校验语句执行，避免运行主入口的最终封存写操作；合成variant路径也仅在新tmp内。所有旧尝试均保留。

## 已关闭问题

### P2：等待/优先的数值类型变化可假通过

原扩展摘要在剔除`r5_lane_priority_enabled`后使用Python字典相等，接受`5.0`与`5`，同样不能区分`1.0`与`True`。因此会在数据并非精确一致时写出`waiting_vs_priority_inputs_checked=true`。独立夹具只把waiting的目标速度`5.0`改成`5`并重新封存，其余不变，原检查未抛错。

修复是使用canonical JSON比较等待/优先、OFF/ON以及half-control的对应非开关输入/参数，保留类型并拒绝非有限值。修复后的原变异被正确拒绝；正常失败前缀夹具仍能生成明确标为failed的候选摘要。

### P2：不同源码的回归日志可与当前freeze混绑

旧regression stdout首行排除了`source_hashes`、`parent_source_hashes`与`legacy_input_hashes`；binder仅比较这条删减投影。相同测试数量、差异文件集合、plan/case/script hash下，源码A的回归日志可以与源码B的完整freeze一起通过。独立探针实际执行binder校验段，复现了该假通过。

修复后stdout绑定独立attempt的完整`source_freeze.json`绝对路径和文件SHA。binder要求它处于新variant的`results/phase5c/regression_attempts`，完整内容等于固定成功freeze，attempt文件、stdout所记SHA和固定freeze字节SHA一致，attempt脚本SHA也与freeze一致；最终包会保存两个attempt文件。修复测试同时确认错源被拒绝、同源控制夹具被接受，避免因缺字段造成无关拒绝的假GREEN。

以上两项联合[RED日志](D:/yanjiu1/keyan1/results/operations/20260913T060723376678Z_phase5c_binder_evidence_review_red_ff160a01/stderr.log)为11 tests、2 failures、0 errors；其后[首次GREEN](D:/yanjiu1/keyan1/results/operations/20260913T060844796584Z_phase5c_evidence_review_green_444c4813/stderr.log)为11 tests、0 failures/errors。

### P2：物理完成而评估失败的合法结果被binder误拒绝

标准replay的`source_execution_status`取自case metadata。`phase5.run_case`可能物理执行为completed，随后后处理出现`evaluation_error`，使case/top validation的`status`为failed。旧binder把replay执行状态与validation评估状态直接比较，会把正确保留的评估失败误判为“重放改变结果”。独立夹具在recording仍true时保留该状态组合，原binder抛出`Replay changed outcome`；[RED日志](D:/yanjiu1/keyan1/results/operations/20260913T061001615622Z_phase5c_evidence_evaluation_boundary_ef5c68a5/stderr.log)为12 tests、0 failures、1 error。

修复后binder用case metadata的执行状态核对标准replay，同时以canonical JSON核对case validation与top variant，评估failed及其错误原样保留。最终14项GREEN包括此合法分支，也继续拒绝把实际失败执行改报completed的重放。

## 其他已核对边界

初读发现的三个扩展摘要核验缺口已在首次有效变异测试前由主任务补齐：completed必须拥有声明的全部completed记录与声明终点时长；对全部OFF/ON调用原配对检查，首例调用原half-control检查；原检测器除包内自报hash外，钉住父版本SHA`aef75a7d79ec19efca36ff0032234e155ff5422fa68e552c3a7a0be9288ce204`。对应截断满窗、未减半cadence、重新封存60秒deadline检测器的变异均被定向拒绝。这些是修复后边界验证，本审查未声称曾对三个旧实现独立跑出RED。

比较helper静态路径要求固定5B正式run evidence SHA，107→110源码数量，精确7文件delta及8→10输入；旧8输入原样保留，新增plan与父原字节案例。17变体原三字段schema保持不变。跨版本初态、私有记忆、物理脚本及数值以canonical JSON核对，唯一新增参数为严格bool True的`r5_lane_priority_enabled`。正式模式必须是不同source，自比较单独标audit；正式声明仍要等对应标准重放。

独立纯函数检查精确允许delta、非声明文件拒绝、旧输入变化拒绝、bool/int与int/float区分、共同记录时间/actor cohort一致、OFF非空前缀要求、ON空前缀unknown以及任意失败配对的全窗delta为null。失败记录中的计划请求可以观察，但不会计入已提交计划。

扩展矩阵为原两案例OFF/ON、首例half-control，以及`r5c_gradual_three_r5_waiting`；只有waiting条目新增`lane_priority_enabled=False`。控制器不接收此离线矩阵字段。扩展摘要只读自己的输入/返回记忆：R5阶段及UNKNOWN计数来自返回memory，形成状态/参考存在也来自memory；不以相互矛盾的临时诊断phase/reference覆盖已记录记忆。失败尾部保留timeline，但不增加已提交时长、计划提交、完成事件或首次稳定参考。

全五actor和三受控actor分别调用同一原检测器；测试证明三车子集成功不会改变全五车的失败值。固定合成轨迹在31秒后才形成连续三车组，36秒确认、46秒达到保持时间：interval保留，但原30秒deadline仍失败，不能因延长到60秒而标成功。参考存在、完成换道和形成判据分别记录；左控制样本速度均值/低速时长按字段名限定口径，没有冒充0.01秒物理采样积分。

binder的独立数据检查覆盖匹配重放、错source path、source before/after hash变化、重复case、case.passed false、遗漏未启动项，以及执行失败被改报成功；异常均被拒绝。静态核对binder要求固定5B parent/replay、17与6项完整尝试、run/replay在新variant内、两run源码等于当前受测freeze、compare/gradual包各自绑定对应run及当前helper脚本，科学验收与phase6始终false。

regression helper对每次尝试创建新目录，不覆盖旧失败；只有测试成功、源码前后相同且无skip时才生成固定成功freeze。旧7个精确fixture输入只在新variant中按hash复用。主任务已经说明旧格式/旧实现尝试将保留为失败证据，正式证明须来自修复后新helper的新回归；本报告不把仍在运行的回归预报为通过。

## 审查边界与下一入口

本结论仅覆盖上述固定helper版本和数据边界，未重新执行控制器语义、SUMO、完整17/6案例、真实标准重放或最终binder主入口。未证明改善、互斥、公平、有限通行、编队恢复或一般安全。前述阶段5科学失败及阶段6关闭仍有效。

正式结果完成后，主任务须使用成功且来源完整绑定的新回归，运行各包标准语义重放，再生成只读比较/扩展摘要并执行最终binder。若上述helper SHA或schema之后变化，应复核受影响边界；最终实例的路径、hash、数量和状态还需在真实包上核对。

## 2026-09-13 06:50 UTC：最终真实包及报告补核

**真实包检查通过，没有新增P1/P2。** 此次读取最终[路径spec](D:/yanjiu1/keyan1/tmp/phase5c_delivery_inputs.json)，核对已完成的两组运行、17+6项标准重放、最终313项回归和报告；没有重复此前14项夹具测试，没有执行车辆、控制器、模型或binder主入口，也没有创建最终acceptance。

新建[只读核验脚本](D:/yanjiu1/keyan1/tmp/phase5c_real_evidence_review.py)从当前binder的AST中仅取真实校验前缀，截止`acceptance`对象及输出目录创建之前；检查前缀不存在文件写入/复制/删除调用，再执行完整只读条件。当前binder SHA为`bb269e2403fd1169dc0ac498d9fd68b1cc58b578f83a855a96536d429542056a`：较上次14项GREEN版本仅在末尾报告快照列表增加通行诊断文档，已复读本次实际校验代码。

本次[wrapper结果](D:/yanjiu1/keyan1/results/operations/20260913T065005580677Z_phase5c_real_final_evidence_review_precision_d454a8c2/result.json)为exit0、3.344秒、stderr为空。[完整独立verification](D:/yanjiu1/keyan1/tmp/phase5c_real_evidence_review/20260913T065005729773Z/verification.json)保存实际绑定、源码/文档hash、逐场景换道表及51条链接；本次核验脚本SHA为`344811e8503aec57c713c7e8f5ecd26a8a3b9a7ef93bd21e2b7669cbe4624115`。第一次只读尝试因审查脚本把报告显示的`5.6s`与保存值`5.599999999999996s`作字面精确比较而拒绝，保留[原日志](D:/yanjiu1/keyan1/results/operations/20260913T064908791014Z_phase5c_real_final_evidence_review_76781f3a/stderr.log)；只修正审查脚本对报告显示数值的1e−9s精度比较，未改原始数据、任何生产/helper源码或历史输出。

|核验对象|实际固定结果|
|---|---|
|5B父包及标准重放|固定父run evidence SHA `6f7ddd2a844f9b58a29bd7efd7b7774d9d3bad5e94809c5f99e72784b51ff192`；固定父replay validation SHA与原登记一致，17项绑定通过|
|[5C原17项run](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/phase5_r5/runs/20260913T061451357664Z_cd3da24b/validation.json)|17已尝试/完成finalize，14物理完成；`competing`、`same_private_state`、`quantized_private_states`的OFF保留失败；339文件，manifest SHA `3155cca5eaa634ead59353a6327a244ae70730f1fa4ee18f4f6bd9d75c37ff34`|
|[对应17项replay](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/phase5_r5/replays/20260913T062619302264Z_135ea687/validation.json)|17个唯一case全部passed；errors/unstarted为空；source before/after一致，物理执行状态与各case metadata一致，评估结果与top逐项精确一致|
|[5C扩展6项run](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/phase5_r5/runs/20260913T062619294263Z_4126e0fd/validation.json)|6已尝试/完成finalize，5物理完成；三车OFF保留失败；207文件，manifest SHA `08e1ab0f619dd404fd048d62c3718838224c55d4fbcbaf14d9939be76ae03f5c`|
|[对应6项replay](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/phase5_r5/replays/20260913T063537973705Z_c407c3ee/validation.json)|6个唯一case全部passed；errors/unstarted为空，来源和原失败状态保留|
|[最终回归](D:/yanjiu1/keyan1/results/operations/20260913T061008877499Z_phase5c_integrated_regression_bound_885174e7/result.json)|313 tests、0fail/error/skip；stdout绑定的完整attempt freeze、固定成功freeze及其字节hash一致；保存脚本、日志hash匹配，当前110源码/7delta及两run源码相同，两run各10输入对应当前冻结输入|

两run的recording均true，engineering/driving均false；标准重放通过没有改写四个OFF失败前缀，也没有把总体驾驶或科学门槛改为通过。原8个新ON的原驾驶/舒适检查均true，与报告的限定口径一致。扩展冻结文件SHA也与报告`a21f8a4782955c4fab47ed91218b51f621f8a4d795b2d307b27f986aca4e682a`一致。

直接读取父/新8个ON的最后committed返回记忆，确认验收表中的换道完成数：single_clear 1→1、competing 0→1、speed_floor 0→0、entered_priority 0→0、front_priority 1→1、reentry 0→0、same_private_state 0→1、quantized_private_states 0→1。原8个OFF共同保存前缀的精确动作/记忆/物理链标记均true；比较包14对完整窗有delta，3对含失败前缀的全窗delta为null。

核对真实扩展摘要的waiting/priority完整状态与驾驶/舒适值、末速、181/0对600/600阻断拍数、170/170 UNKNOWN、上方0.5s提交/5.6s完成、11.7s稳定参考但无实际形成增量、下方19.1s稳定参考/20.3s首次实际增量，均与验收所述相符。全五actor和受控三车的whole success均false，持续形成interval均为空，原30s期限/确认后10s保持不变。更细的483拍原守卫拒绝及可见锚点丢失归因，由已读取的[最终通行诊断](D:/yanjiu1/keyan1/docs/phase5c_liveness_diagnosis.md)及其独立原trace核验支撑；其最终SHA `2bb2f83b958b821981f9018f65d5527d0f75a378fd6e425c7c3cf6fcdd3c63ce`，末尾扩展标准重放绑定已补齐。本次没有冒称重新运行该诊断或物理模型。

另复读[摘要字节核验helper](D:/yanjiu1/keyan1/tmp/phase5c_check_summary_replay.py)，SHA `7aba2376066f209d6044a9ba967c70351d96ac5071b7a26ada6e5f97e0a72156`。独立再次逐文件hash，确认比较首包/异cwd重放的7文件、扩展摘要首包/异cwd重放的5文件全部集合与字节一致，并与其各自封存manifest及verification记录相同；没有仅相信saved `passed=true`。这仍是数据脚本重放，和已经单独绑定的标准语义重放分别成立。

对最终[验收](D:/yanjiu1/keyan1/docs/phase5c_lane_priority_acceptance.md)、[重放索引](D:/yanjiu1/keyan1/docs/phase5c_replay_index.md)、[下一入口](D:/yanjiu1/keyan1/docs/phase5_next_entry.md)共51处本地Markdown链接逐一检查：全部绝对路径且目标存在；本次读取的三份正文在核验前后hash一致。正文保持“局部单车通过改善、三车未形成、科学未通过、阶段6关闭”的限定，没有把14/5个完整执行或23项重放解释成全部驾驶/形成成功。

本补核允许主任务按既定spec执行最终binder。最终acceptance目录及最终文档快照仍由主任务创建并验证；本代理在写入此补记后停写，避免封存期间变更文档。
