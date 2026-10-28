# 阶段5D：harness、重放与交付证据独立审查

审查日期：2026-09-13。当前结论：正式运行前审查、两个新正式包、两份标准replay共12case、三来源比较的结构/字节/重封篡改及新实际跨cwd执行均已独立核验通过。两个P2均已关闭：原回归skip门禁由v2修正；旧snapshot未跨cwd的问题由另一次真实chdir执行补齐。旧失败日志和旧snapshot保持原样。最后交付binder已审查增强的receipt/wrapper绑定，待root运行最终封存；科学验收与阶段6仍为 false。

## 范围与约束

- 阅读工作区 `AGENTS.md`、冻结的 `docs/phase5d_local_game_plan.md`，以5C封存来源为父实现，不使用不存在的 git HEAD/SHA。
- 审查 `variants/phase5d_local_game/run.py`、`experiments/phase5_r5.py`、`experiments/phase5_r5_replay.py`、`tests/test_phase5d_harness.py`。
- 独立审查 root `tmp/phase5d_compare_games.py`、`tmp/phase5d_regression.py`、新增 `tmp/phase5d_regression_v2.py` 及 `tmp/phase5d_save_acceptance.py`。
- 没有改控制器、核心算法、原始实验、原验收证据或生产测试；独立探针仅写入 `tmp/phase5d_evidence_review_tests.py` 与新的隔离测试目录。新短测/合成数据不属于正式效果证据。

审查版本的实际 SHA256：

| 文件 | SHA256 |
|---|---|
| `tmp/phase5d_compare_games.py` | `c899dd7cda23364afdbc32583cc5354a6015cdb8d16267f7eee9af43c238a607` |
| 原 `tmp/phase5d_regression.py` | `e74ac541a6ca8a041248f9f60dfe192c46e98f9a6724b7512d119f888054fa58` |
| `tmp/phase5d_regression_v2.py` | `f9340ba744fae558b04b096de398f24e4695e1803fdafdd9a7bbf3b49253bc22` |
| `tmp/phase5d_save_acceptance.py` | `2cf9b7035db247af78b9fe4e2ced46cd5ced26e69683598c2e2b89af3d1660ff` |
| 已有 `phase5d_source_freeze.json` | `41c526b8ff5b427415b4fecd9a9273d4ca33fe20f4a76a45395b5cde9ffff76d` |

## 规格与代码判断

1. CLI及参数工厂严格接受 fixed/minimax/stackelberg 枚举。默认 fixed 的参数与模式矩阵保留父结构。独立探针加载 `clone_provenance.json` 指向的实际5C父 `experiments/phase5_r5.py`，核对 enabled/lane_priority 四种组合：默认参数相同，去掉预登记6个游戏字段后新模式参数也相同。这个检查不是仅比较新工厂的默认调用与显式 fixed 调用。
2. 新模式仅写入 `r5_enabled=True` 且 lane priority 启用的普通ON与半控制步变体。OFF及三车旧waiting基线均不获得游戏参数；比较脚本独立列出的6变体矩阵与 harness 三种模式完全相同。
3. 新计划是唯一额外 required input。source/code/input三个精确文件集、当前运行源码、冻结案例字节、案例初态、模式矩阵、模型与控制参数都有绑定。标准重放要求顶层显式 `waiting_policy`；缺失、大小写或未知值不能成为默认值补救。
4. `compare_private_record` 在常规物理容差比较前，对全部 `waiting_game` 递归做精确值和类型检查，并核对诊断存在性。独立探针覆盖 float→bool、float→int、int→bool、bool→int、嵌套字段及双向删除/新增，均拒绝。普通参数沿用原 `compare_tree` 的数值语义，但 bool不会被当作数字；比较helper对新增参数采用JSON规范表示的精确类型比较。
5. `run_phase5_r5()` 的 `except BaseException`、前缀重建与 `finally` seal段和实际父源码逐字相同。新模式传递不改变既有中断尝试记录、已提交拍数、失败状态或封存路径；此项是代码差异检查，完整失败回归沿用下述347项实际记录。
6. 比较helper固定父扩展 manifest `08e1ab0f…ae03f5c`、扩展案例SHA `a21f8a…e682a`，绑定原检测器与两个已审helper的完整SHA；独立probe重新核验 `phase5c_gradual_summary.py` 为 `a39c2731…8c445`、旧 summary 为 `09efc4dd…97658`。
7. 三来源比较要求新源码相对父仅7个预登记delta，两新模式的源码与输入相同，原有输入hash不变且只增加计划。它逐案例绑定物理初态、记忆、私有状态来源、原模型与数值参数、时钟及road；OFF/旧waiting共同已记录前缀作完整记录相等检查，并单列共同记录数和各自长度。
8. 完整窗差分只发生于父、新案例均 `execution_status=completed` 且完整记录/终时覆盖通过时；失败案例的差分是 null。逐车均速是已提交控制步左端速度按时长加权；失败尾仍留timeline，不能补零或外推为全窗。独立合成probe验证游戏统计、拒绝计数和episode clear都不提交失败尾，同时仍保留该尾的请求和动作。
9. 原检测器全actor结果和3受控车子集分别列出。独立只读实际固定父扩展包检查成功：6案例中5完整、三车OFF一条失败前缀；对应5车与3车检测均有独立字段；运行包全部文件集合/hash前后相同。
10. 比较helper仅导入固定摘要/离线检测器，不调用在线控制器。输出采用新增目录与 `open('x')`；禁止覆盖或嵌套来源目录，末尾再次验证三来源不变，保存自身与两个helper快照。`semantic_replays_bound=False` 明确表示比较自身不替代标准语义重放。跨cwd快照整包重建仍需正式数据产生后实测。
11. 最终binder静态核对原347日志/完整attempt冻结、113源码、固定父与两个新6案例标准重放、实际来源manifest、模式/案例/输入及比较字节绑定；自身不把原驾驶或科学失败改写为通过。它要求comparison与snapshot是不同目录，外部byte check的first/second及manifest必须指向实际两份结果。独立probe用真实父replay通过绑定，再在新副本重封后分别改变case通过标志为整数1、重复case、把失败执行重标为完成、伪造source hash，四类均拒绝，原replay封存前后不变。完整binder main尚待正式新包，不能以这个局部probe冒称全交付成功。

## 已发现问题及关闭依据

**[P2，已在v2关闭；原版本保留] 回归有skip时返回成功。** 原 `tmp/phase5d_regression.py` 的成功freeze分支要求 `not result.skipped`，末行退出码却仅检查 `wasSuccessful()` 与源码不变。真实 `main()` 对隔离合成workspace运行1个注入SkipTest，输出 `tests_run=1, skipped=1, source_unchanged=true`、不写成功freeze、但 `SystemExit(0)`；独立要求非零的断言失败。

root新增v2，在退出条件加入 `and not result.skipped`，并另用v2 schema、attempt目录与freeze文件名。未改原helper或原347成功freeze。相同合成probe随后通过：skip导致非零且两个成功freeze文件均不存在。修复仅属工具门禁，不是再次执行347项。

旧版本问题没有作用于已经完成的真实整套回归：审查者直接读 `results/operations/20260913T110036350132Z_phase5d_integrated_regression_bound_e04df533` 的result/stdout，确认 exit0、279.921s、347测试、0失败、0错误、0skip、源码不变。最终binder严格要求0skip并绑定原helper与原freeze，因而可以保留这份已有证据。

## 独立验证日志

全部使用指定 CPython3.12、`-I -B -S`，通过 `scripts/run_logged.py` 留新目录和外部180s超时：

| 日志目录，均相对root `results/operations/` | 结果及含义 |
|---|---|
| `20260913T110707202509Z_phase5d_independent_evidence_red_cee72143` | exit1；8项中7通过、1有效RED，复现原skip退出码缺陷。 |
| `20260913T110900327210Z_phase5d_independent_evidence_v2_green_346424b3` | exit0；8项通过，原检查加v2 skip门禁。 |
| `20260913T111023345454Z_phase5d_independent_evidence_binder_green_42ba5a65` | exit1；新增probe误用run专属 `verify_source` 检查replay，因replay没有code_hashes报错；这是探针错误，没有归因于生产逻辑。 |
| `20260913T111100643579Z_phase5d_independent_evidence_binder_green2_263c0786` | exit0，6.485s；修正为通用seal检查后9项通过，包括binder四类重封篡改拒绝。 |

9项探针套件自身没有skip；其内部故意执行的1项合成SkipTest用于检验v2拒绝条件，不计作正式回归通过证据。

## 正式运行前审查结束时的补核入口（历史状态）

截至本版没有未关闭的P1/P2生产或工具问题；原regression v1禁止用于含skip成功判定，新增v2为后续工具入口。允许使用已封存113源码进入计划中的两包正式运行。

仍需获得两个新6包及标准replay、三来源comparison和异cwd快照整包字节核验、最后binder输出后追加本报告：核对真实失败前缀/无改善、游戏启用/回退与实际动作、完整窗限定、5actor/3受控检测分列，以及来源hash前后不变。仅完成这些补核后才能评价“注册实验交付完成”；本报告当前不作该声明。

## 正式实包补核：两个新模式

已独立核验封存来源：

| 模式 | 新variant `results/phase5_r5/runs/` 下的run | evidence manifest SHA256 |
|---|---|---|
| minimax | `20260913T111001467229Z_2d9c8d5f` | `064815d48e65e679f8819f490891502c5568019f1d6bc1f2d9c4d421dd853c48` |
| stackelberg | `20260913T111103953169Z_c63ac16e` | `64f52f4dc29c8fd6a3d33d4705156448e31e4c8f5d3f79ccdc4c4b5de753ec39` |

两包各211封存文件、113源码、11输入，均6attempt/5complete/1三车OFF失败。新模式互用同一源码及输入；仅计划为新增input，原数值参数、物理初态、私有状态和road与父一致。原OFF/旧waiting的全部trace（含失败尾）与父精确相等，既不是仅动作相等，也不止完整共同前缀。

`tmp/phase5d_formal_evidence_probe.py` 使用独立的分段线性速度积分重算全部已记录收益矩阵的两方代价、完整BR集合、minimax最坏动作见证及Stackelberg悲观leader/follower选择，没有运行在线控制器。两个包最大代价重算误差分别为 `2.842170943040401e-14` 和 `3.019806626980426e-14`。所有已采用不同请求均有原5.5s守卫通过证据；最终动作等于记录的applied request；来源全部文件hash前后相同。

| lower在60s三车ON中的已提交拍数 | minimax | stackelberg |
|---|---:|---:|
| game诊断 | 198 | 202 |
| 矩阵求解 | 188 | 192 |
| 选中请求不同于fixed | 106 | 127 |
| 不同请求被原守卫拒绝 | 27 | 47 |
| 模型请求采用，包含恰好等于fixed | 128 | 113 |
| 实际请求改变 | 79 | 80 |
| fallback诊断 | 70 | 89 |

helper新增的 `different_model_request_decisions` 和 `different_model_request_guard_rejections` 已与独立逐拍计数一致。它们消除了 `model_guard` 与 `fixed_guard` 指向同一次固定请求验证时的计数歧义；原两个诊断计数仍不能相加解释为独立验证次数。专门的同fixed拒绝合成probe确认两个旧字段可以各为1，而different两个字段均为0。

独立审查结果分别在 `results/phase5d/independent_minimax_20260913T112523016157Z` 与 `independent_stackelberg_20260913T112523112377Z`；wrapper为 `20260913T112509841114Z_phase5d_independent_minimax_formal2_90290842`、`20260913T112509853119Z_phase5d_independent_stackelberg_formal2_a8f47718`，exit0，13.515/13.625s。

保留两条首轮probe失败日志 `20260913T112356781076Z_phase5d_independent_minimax_formal_5705d61b`、`20260913T112418003894Z_phase5d_independent_stackelberg_formal_9726ade8`：探针错误地要求守卫相减得到的checked_s严格等于字面值5.5，实际存在 `5.499999999999998`；修改的仅是独立probe的1e-12数值比较，原源码、原守卫或证据均未改。这不是安全时域缩减或算法失败。

## 三来源结果与重封篡改补核

实际comparison为 `results/phase5d/comparison_formal_20260913T1122`。本次冻结helper SHA为 `a4693a829cf9203f5621145d797ea61a83286c4fcf7bde43bfc8d38cf005e1a4`；binder引用快照列表更新后的SHA为 `7e60942f129f7e9324cab66c3bdb6490fe71536b106671e97f5f2f9d103fe8eb`。原审查版本SHA在前表保留，不混称为同一文件版本。

三种方法的lower左控制点加权60s均速分别是2.7900869038826177、2.790054490842116、2.7900555873373496 m/s，不能声称全窗均速改善。episode清除记录分别为18.1s/0.03235983596892728m/s、19.8s/1.849397485095146m/s、20.2s/1.7011622665415613m/s；这是清除时刻局部速度差，不能解释为更早清除或换道成功。三者lower均未完成换道，upper均完成1次；全5actor与受控3actor的 `success/local_success/whole_cohort_success` 均false，`intervals` 与 `candidate_intervals` 均为空。

每个新模式的OFF single200、OFF three27、旧waiting600条全trace与父相同；27条包含26完整拍和失败尾。OFF three完整窗差分仍为null，没有补零。

`tmp/phase5d_comparison_evidence_probe.py` 对实际minimax包分别新建四份副本，修改后重算封存manifest：顶层mode替换、游戏数值改为bool、继承舒适参数改值、加入未登记源码。四类副本内外hash校验本身通过，而真实comparison main均按对应约束拒绝，未创建成功输出；三个原run的文件集合/hash仍相同。该探针同时通过完整窗/统计范围检查与同fixed守卫不重复计入different检查。

**[P2，已由下述新attempt关闭] 旧snapshot未证明异cwd。** `comparison_snapshot_replay_20260913T1124` 与正式comparison的全文件集合/字节一致，外部bytecheck也指向正确两份输出。但是wrapper `20260913T112420287164Z...66b05811/result.json` 的真实child cwd为 `D:\yanjiu1\keyan1`；`run_logged.py` 固定child cwd使父工具指定 `D:\yanjiu1` 失效。独立probe `20260913T112751794841Z_phase5d_independent_comparison_formal_9d9f76cf` 为4项3通过/1有效RED，精确复现这个执行证据缺口。旧快照和日志保持不变，其本身仍不满足跨cwd条件；不是把旧报告改写成已跨cwd。

## 最后受影响核验：标准replay及真正跨cwd

两份标准replay现在均已完成并独立核验封存、wrapper日志与来源：

| 模式 | 新variant `results/phase5_r5/replays/` 下的replay | replay evidence manifest SHA256 |
|---|---|---|
| minimax | `20260913T112041226929Z_ba12ddc8` | `0155e9159d725a57c3eda90f2762a634d3452873ec2761152d67300cf150d27d` |
| stackelberg | `20260913T112236784168Z_4ee72d26` | `b9bc09466e54d88fae47b11e9b12c18f55f04822bd7fe8c6cbbd8cf29ee10621` |

两份共12case的trace、isolation、detection重建均passed；实际执行源码等于封存code，冻结input相同，source_before/source_after及实际来源manifest均绑定。两份的 `r5c_gradual_three_r5_off` 均仍为 `source_execution_status=failed`，trace的 `failed_execution_prefix=true`，没有把物理失败改为成功。标准重放成功只证明记录可重建，不能推翻原工程/驾驶失败。

新 `tmp/phase5d_crosscwd_replay.py` 先解析绝对script/cwd/receipt路径，再真实执行 `os.chdir(D:/yanjiu1)`，随后通过runpy运行正式comparison的原 `script_snapshot.py`；传递原三个来源与新输出目录，未改快照脚本。finally记录真实执行前/后cwd、脚本前后SHA、命令参数及状态并封存receipt。审查版本launcher SHA `24e6ce77591e9239d08057e562b5f3f2ff5afaac9930b4c8a396135d53af5a44`。

新执行证据为：

- wrapper `results/operations/20260913T113552974106Z_phase5d_actual_crosscwd_snapshot_886c702c`；初始child cwd依旧为项目根目录，但launcher内部执行前后actual cwd均明确是 `D:\yanjiu1`。
- `results/phase5d/crosscwd_receipt_20260913T1132`；receipt manifest SHA `a2fb59f19be7c3210fb50e7bc14292f6e6a9041a6fe509a0fe3251e225ced317`。请求/实际cwd、固定来源、输出、脚本SHA及launcher快照都符合。
- 新输出 `results/phase5d/comparison_actual_crosscwd_20260913T1132`，完整文件集合/字节与正式comparison一致，两份manifest均为 `c01f65db0b230250464fb880345ae9dcdd23aa7035acb3d29f5ea0a1ee4ad481`。
- 新外部核验 `results/phase5d/comparison_actual_crosscwd_bytes_20260913T1137/verification.json` 指向上述真实两份输出，passed=true、exact_file_set_and_bytes=true。

独立最终probe `tmp/phase5d_final_replay_evidence_probe.py`（SHA `f2a09d92bb8d08f78e0bc6f3ac869f6961a448f0cf1c39a6e2ee4e6fba9b8db4`）仅复核受影响的重放绑定及新跨cwdreceipt/字节，不重跑矩阵、四类篡改或347回归。wrapper `20260913T113752097479Z_phase5d_independent_final_replays_f6e75893` exit0/3.015s，结果封存在 `results/phase5d/independent_final_replays_20260913T113755079142Z`。来源、replay和新跨cwd封存前后不变。

最终binder的新版本SHA `f21b26f779db26d4821be7c843aeecccfcbf495b043e28b6e6ead9e9e3f8bb89` 已增加receipt封存、实际执行前后cwd、原snapshot脚本SHA、完整来源/输出参数、launcher快照、真实wrapper命令及cwd、runner与日志hash、stdout完成记录绑定，并将receipt与wrapper快照纳入交付。不再仅凭字节相同宣称跨cwd。静态审查未发现新P1/P2；最终binder main产生的交付目录由root下一步封存后核对。

当前没有未关闭的P1/P2。工程记录与预登记比较交付的证据要求已满足审查范围；未形成、两份OFF失败、lower未完成换道、均速无改善以及单一活跃三车场景的外推限制都必须继续保留。
