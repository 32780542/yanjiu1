# 阶段 5：A 局部 cost 与 B 固定邻域规则的副本隔离设计

2026-09-13。本单元只核查复制、运行、重放与比较边界；没有启动实验或改变 A 的生产代码、配置和旧结果。A 的正式运行继续使用其冻结快照。

## 结论与实际检查

复用原阶段 5 runner/replay 的独立副本方案可行。`research.common.ROOT`、`run.py.ROOT`、`scripts/run_logged.py.ROOT` 都由各自文件位置确定；无需修改公共基础设施。当前 A 的 `code_manifest()` 含 94 个文件，阶段 5 另有 5 个运行输入，合计 99 个复制文件及新建 `tmp/`，足以执行阶段 5 和独立重放。

只读清单保存在 `tmp/phase5_comparison_design/inventory_20260912T183125Z_2dec2c8a/inventory.json`；日志为 `results/operations/20260912T183124842619Z_phase5_comparison_inventory_0f72b47d`。清单确认 94 个源码/配置文件、5 个阶段 5 输入全部存在；登记所指向的 29 个外部 MATLAB 源文件哈希全部一致，检查前后 A 源码清单未变化。

已检查主代理的 `tmp/phase5_clone_workspace.py`：只从明确指定的 `code_snapshot`、`input_snapshot` 复制经过 SHA256 核对的条目，拒绝现存目标，检查解析后的源和目标包含关系，创建独立 tmp 并保存 clone_provenance。当前源使用 A 正在运行的固定代码/输入快照，这证明复制来源，并不宣称 A 的实验已经完成或通过。

当前目录约定如下；新目录必须明确命名，已存在目录不重用。

| 工作区 | 用途 |
|---|---|
| `D:/yanjiu1/keyan1` | A 原始局部 cost；正式运行期间生产代码冻结。 |
| `variants/phase5_rules_front_first` | B1，固定一种 front-first 选择规则。 |
| `variants/phase5_rules_corner_first` | B2 建议名称；从冻结的 B1 实现复制，只改变已声明规则枚举。 |
| `variants/phase5_cost_holdout` | 已创建的 A 留出集副本，仅六个随机 seed 改为 6111/6112、6211/6212、6311/6312。 |

## 复制清单

必须按指定源快照的 `code_hashes.json` 复制全部 94 个条目，保持相对路径。它包含 `run.py` 和 `research/perception/noa/models/safety/simulation/experiments/tests/scripts/configs` 中的实际文件；不要另用递归复制整个研究目录替代清单。

阶段 5 固定输入为：

1. `scenarios/cai2024/bottleneck.net.xml`
2. `docs/parameter_registry.csv`
3. `docs/phase4_completion_acceptance.md`
4. `docs/phase5_implementation_plan.md`
5. `docs/noa_staggered_formation_research_plan_2026-09-10.md`

另建 `tmp/`，复制操作的来源、哈希和脚本哈希保存在副本根的 `clone_provenance.json`。使用普通文件复制，不用指向 A 的硬链接、符号链接或目录联接。建议复制结束后再次逐文件核对目标 SHA256、文件集合和两个清单无冲突，再允许修改方法文件。副本根若需要 AGENTS.md，应明确当前副本路径及 A 只读，不能把原检查点中的固定 A 工作目录当成副本运行目录。

不要复制旧 `results/`、旧 `tmp/`、`.git` 或预生成 `.sumocfg`。尤其 `smoke.sumocfg` 与 `mcp_probe.sumocfg` 的 tripinfo、summary、fcd、lanechange 和 log 已写入 A 的绝对输出路径；复制后运行会写回 A。阶段 5 bootstrap 直接用 NET 和新建 routes.rou.xml，不需要这些文件。

准备 B2 时无需先跑一轮 B1 大实验来获得代码快照。可在 B1 独立进程中将其当前已定稿的 `code_manifest()` 和上述输入封存在新的 `tmp/prepared_source_<id>/`，使用与 run 相同的 code/input hashes + snapshots 结构，然后让现有 clone 工具读取该明确目录。准备快照要记录 `snapshot_kind=prepared_method_source`，核对复制前后源码及输入哈希；不得把它标成完成的实验。之后 B1 与 B2 各自独立封存运行，不再原地改选择规则。

## Runtime 与路径边界

每个副本必须由独立的 `python -I -B -S` 进程运行自己的 `run.py`。它会把本副本加入导入路径、切换 cwd，并将 TEMP、TMP、TMPDIR、MPLCONFIGDIR、XDG_CACHE_HOME 全部指向本副本 tmp。各副本使用自己的 run_logged.py，操作日志自然写到各自 results/operations；Windows 私有 Job Object 管理各自子进程，SUMO 窗口保持隐藏。

不能先 import A 再在同一 Python 进程里切换 cwd 或 sys.path 去运行 B。`research.common` 等模块会留在 sys.modules；随后可能继续使用 A 的 ROOT、模型或控制器。干净进程里只执行一次目标副本的 runtime setup 是允许的。

还有一个已确认的守卫范围变化：原 verify/test_foundation 只排除 `ROOT.parent` 下、ROOT 外的导入路径。副本的 ROOT.parent 是 `keyan1/variants`，所以该旧守卫不覆盖更上层的 A 根 `keyan1`。不能只凭这个旧测试宣称副本导入隔离通过。

为此提供 `tmp/phase5_comparison_design/check_module_origins.py`。它要求新进程和明确 variant，import 该副本的 run 模块完成 setup，不调用 main，再加载阶段 5、时钟、控制器、审计、重放、模型及感知模块。它验证所有已加载项目模块的 __file__/namespace path 均位于目标副本；sys.path 中没有 A 根或兄弟副本；cwd、common.ROOT 和五个 tmp 环境变量均正确。可选 `--output` 只接受副本外的新 JSON，拒绝覆盖。

示例只做导入审计，不启动仿真：

```powershell
& 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -I -B -S `
  'D:/yanjiu1/keyan1/tmp/phase5_comparison_design/check_module_origins.py' `
  'D:/yanjiu1/keyan1/variants/phase5_rules_front_first'
```

该脚本的四项进程测试已通过：正常 holdout 副本、误传 A 根、显式注入 A 祖先导入路径、缺少 -I。红灯和绿灯分别保存在 `results/operations/20260912T183559337700Z_comparison_origins_red_c0eca0a0` 与 `results/operations/20260912T183728600673Z_comparison_origins_green_b22b838f`。这验证路径审计，不证明 B 算法正确。

SUMO 的 bootstrap 使用本副本 NET、新 run 内 routes.rou.xml/stdout/sumo.log、UUID TraCI 标签和默认独立端口；同一主机的独立 Python 进程不会共享 TraCI 连接字典。每个副本都使用 configs/tools.json 指定的同一 CPython、SUMO 1.27.1 和工具库，外部安装目录仅作共同只读依赖，不复制或修改。`run.py` 的隔离和临时目录设置必须发生在启动 TraCI 之前；单独 import common/phase5 不等于完成这些设置。

## Registry、verify 与受影响测试

新增规则枚举或改 seed 后，复制来的 parameter_registry.csv 仍可能保留 A 的旧值。冻结副本前应更新本地登记表，使 configs、metadata 和输入快照一致。直接复用 `run.py registry` 只需额外复制 `docs/cai2024_source_parameters_2026-09-10.json`；它读取原 29 个外部源作哈希检查，写入副本 docs/parameter_registry.csv 与副本 results/phase0，不改原参考源。

`run.py verify` 不是只核对阶段 5。除上述 source snapshot，还需要四档需求各自 `.csv`、`.types.csv`、`.rou.xml` 共 12 个文件。当前明确值为 q=1250/1500/1750/2000、seed=20260910；完整路径和 SHA256 已在 inventory 中列出。阶段 5 小案例不用这些需求文件。

原 `run.py test` 会发现依赖 phase0/environment、mcp_probe、phase1/smoke 与 demand_manifest 的 artifact 测试。最小副本没有这些旧结果，不能把缺少旧结果误报为 B 算法失败，更不能复制 A 的成功验收文件冒充副本刚通过。按本次授权只执行受影响的控制器、时钟、感知隔离、阶段 5 detector/recording/replay 及新增规则测试，明确列出范围。需要基础完整验收时再在副本独立生成相应基础证据；预生成 SUMO 配置必须在副本重建。

## 重放规则

每个 run 必须由所属副本的 `run.py phase5-replay --run-dir <明确run目录>` 重放。`output_path()` 限制结果在该副本 ROOT 以内；从 B 重放 A 路径会被拒绝，这是正确隔离。用新的同方法副本直接重放另一个根下的旧 run 同样会被拒绝，需要明确的整体恢复工作区，而不能临时关闭路径检查。

重放要求当前 code_manifest 与该 run 的 code_snapshot 完全一致，包括 tests/scripts/configs。因此每个方法在正式 run 前先完成实现、测试、登记并冻结；run 期间或之后改测试文件也会造成当前代码绑定拒绝。后续调参、新 seed 或新规则均用新副本/新快照。不能为复用一个目录而跳过 manifest 或放宽 replay tolerance。

重放从所属副本的 phase5.parameters(enabled) 严格核对完整 model/p/policy；新增的规则枚举应来自该副本冻结配置，由既有 parameters 合并，并进入日志。禁止只在调用层临时塞一个 metadata 参数、环境变量或未封存 monkey patch。B1/B2 应共用实现，仅配置枚举不同；A 保留原算法，不为了匹配 B 元数据而回写。

clone_provenance 不在原 runner 的 code_manifest/五项输入中。跨方法分析应在一个新的比较包中保存其副本、哈希与 run 关联，不要往已封存 run 增添文件后再重封存旧结果。各 run 的代码、参数、初态和证据哈希本身仍是方法实际执行内容的依据。

## 跨副本汇总的必要等价检查

| 项目 | 必须核对的内容 |
|---|---|
| 显式来源 | 方法名、副本 ROOT、run_id、clone 来源、code/input/evidence manifests；每个完整或失败前缀包先独立重放。不得用 latest 选择研究证据。 |
| 初态与案例 | 逐 vehicle state 严格相同：物理时间、x/y、航向、vx/vy、执行器状态等；同 case kind、seed、duration、controlled/scripts、道路与模型尺寸。不能只比较 seed 或车辆数。 |
| 需求/扰动 | 同一比较中的脚本逐项相同。扰动与无扰动成对分析仅允许预先声明的 event speed schedule 差异，并保持其余初态、clock、policy 和 switch 相同。 |
| 动力学与安全 | 完整 model_parameters、p、基础 NOA、安全门槛、预测时域、执行器滞后、jerk/加速度限制、bootstrap 外部 minGap 全等；只排除预登记的方法选择字段。 |
| 时间网格 | 同计划时域及完整度；普通 .1 s 控制/感知、.01 s 积分；半控制 .05 s 同步修改 policy 的 control/perception 周期，半积分 .005 s。用物理时间比较，先各自扣除 SUMO bootstrap offset。验证全部公共时刻与起止时刻，不用任意插值隐藏缺样。 |
| 检测口径 | phase5_detection.py 及默认 15/30 m、5 s 确认、30 s 初始期限、确认后 10 s 保持、三组容差敏感性全部相同。只对已提交帧检测；失败尾与未启动变体单列。 |
| 结果定义 | geometry/actual jerk/comfort、同记忆隔离 stride 与非空洞正例、恢复/参考出入事件、工程与科学 gate 同一实现；A/B 任一失败、未形成和无改善均保留。 |
| Off 负对照 | 对同一初态/时钟，所有方法的 off 完整输入、记忆、动作和物理轨迹应一致。若 off 已不同，停止将 on 差异归因于参考选择。 |
| 汇总分母 | 按全部计划案例列成功/失败/未完成数；不能只在成功子集汇总改善。失败前缀可比较共同完整时域的诊断量，但不得称完成整个案例。 |

允许差异清单必须是逐文件、逐参数的有限清单，而非“noa 下都可改”：

- A 与 B：允许 `noa/formation.py` 中局部邻域/参考选择实现，或明确新增的局部规则模块；允许 configs/phase5.json 的固定选择枚举与必要来源说明；允许相应新增/受影响测试。其余基础 NOA、感知、物理、安全、时钟、runner、detector、audit、replay 的文件哈希保持一致。若确需改候选资格或保持逻辑，应单独列作方法变化，不能隐藏在“只换排序”描述里。
- B1 与 B2：同一规则实现与测试，原则上只允许固定枚举 front-first/corner-first 变化；所有数值增益和安全参数相同。
- 同一方法的 development 与 holdout：只允许 `configs/phase5_experiments.json` 中预登记的六个 seed 及其登记行变化；实际测试集变化不进入同一成对比较。每个 heldout A/B 方法仍需相同六个 seed 与逐状态初态。
- 登记表与方法说明可按上述明确字段更新；原参数值、出处与安全门槛不能随方法悄悄变化。新比较包记录完整 hash diff，并人工/程序核对 diff 内容均属于该清单。

## 有限探索与留出集

先声明 B1/B2 的选择优先顺序、并列几何处理及失败退出规则；探索次数、案例集合与停止条件预先封存。保留全部尝试。development 的 3/6/12 各两个 seed 只支撑这六个案例的比较，不能据此宣称普遍改善或串稳定。

留出集已指定 6111/6112、6211/6212、6311/6312。可以在不可改的代码/seed 下提前计算 A 留出集，但在 B 方法选择和所有参数冻结、预登记完成前不读取或使用其结果来选规则。B 留出集也必须从最终冻结的方法副本派生；只跑 B 留出集而没有同初态 A 不能构成 A/B 对照。

扰动传播采用同方法、同 switch 的实际扰动/无扰动速度轨迹相减，明确时间窗、速度定义、Δv 峰值与 L2/RMS、实际 event 响应分母；零分母保留 null。相对 5 m/s 的偏差与道路初始前后次序只能作诊断，不能替代成对扰动响应或证明真实参考链的串稳定。

下一步由主代理先完成各副本规则与登记、运行模块来源审计和受影响测试，再冻结并运行；本设计没有执行 B 仿真或更改 A 的结论。
