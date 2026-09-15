# keyan1：无通信 NOA 交错编队研究

阶段4已在既定小案例门槛内通过，M1完成：完整真实SUMO套件14个普通案例通过，补充6个采样变体及3项比较通过，本次141项测试与固定重放通过，见[阶段4验收报告](D:/yanjiu1/keyan1/docs/phase4_completion_acceptance.md)。补充证据封存缺口已完成复核；原急刹压力案例的碰撞和旧失败日志全部保留。主车辆运动为简化运动学与分段二次贝塞尔，编队保持关闭，没有交通效率或节能改善结论。

当前规格（2026-09-11第六版）：主模型为简化运动学与分段二次贝塞尔，保留速度、加速度、等效转向、简单响应和车身几何约束。感知只做有限范围内理想观测，范围内允许状态精确、额外测量延迟为零；不考虑遮挡、噪声、漏检或传感器失联。无通信、局部信息隔离、连续运动和失败保留要求继续适用。

## 研究入口

- [完整科研方案与分阶段 AI 执行步骤](D:/yanjiu1/keyan1/docs/noa_staggered_formation_research_plan_2026-09-10.md)
- [MATLAB 源码参数登记表](D:/yanjiu1/keyan1/docs/cai2024_source_parameters_2026-09-10.json)

## 工作目录约束

唯一研究根目录为 `D:\yanjiu1\keyan1`。所有新代码、配置、文档、临时文件、日志和仿真结果均写入本目录。父目录已有研究代码属于废案，不复制、不导入、不作为测试或结论依据。

允许的外部只读输入为用户提供的两篇 PDF 和 `D:\matlab_huipu_2000` 的论文相关改编源码。已安装的 `D:\yanjiu1\SUMO\sumo-1.27.1` 与 `D:\yanjiu1\SUMO-MCP-Server` 可作为工具依赖使用。源码中的参数和方法均须区分与论文一致的内容、改编差异和待补数据。

## 下一阶段

阶段5现有方案已由 Phase5G 简单局部 if/else 编队路径补充：车辆不通信，只使用有限局部观测和本车记忆，不做全局槽位分配或中心调度；场景仅含受控普通车辆，没有障碍车、背景车或脚本慢车。纵向规则跟随局部最近前车，换道规则只允许局部后排车在安全守卫通过时向唯一较少车辆的相邻车道移动，每辆车最多一次编队换道。实现、完整回归、证据封存及精确重放已经完成，但固定六车案例仍未形成编队，也未通过30 s形成加10 s保持的科学门槛。因此阶段6仍关闭，不声称交通效率、通行能力或能耗收益。当前事实和可重放入口见[检查点](D:/yanjiu1/keyan1/docs/phase5_checkpoint.md)。

## 本轮产物

- [阶段4当前验收、固定运行与重放入口](D:/yanjiu1/keyan1/docs/phase4_completion_acceptance.md)
- [修复前后对比PNG](D:/yanjiu1/keyan1/results/phase4/completion_20260911/figures/phase4_completion.png) · [SVG](D:/yanjiu1/keyan1/results/phase4/completion_20260911/figures/phase4_completion.svg)
- [收尾独立审查](D:/yanjiu1/keyan1/docs/phase4_closure_review.md) · [当前交付清单](D:/yanjiu1/keyan1/results/phase4/closure_20260911/delivery_manifest.json)
- [阶段4轨迹与失败案例PNG](D:/yanjiu1/keyan1/results/phase4/figures/phase4_motion.png) · [SVG](D:/yanjiu1/keyan1/results/phase4/figures/phase4_motion.svg)
- [独立NOA模型与证据语义](D:/yanjiu1/keyan1/docs/phase4_model.md)
- [初始化专项审查](D:/yanjiu1/keyan1/docs/phase4_bootstrap_review.md) · [失败证据复核](D:/yanjiu1/keyan1/docs/phase4_evidence_review_followup.md)

- [阶段3验收与重放入口](D:/yanjiu1/keyan1/docs/phase3_acceptance.md)
- [二次贝塞尔实际轨迹与误差](D:/yanjiu1/keyan1/results/phase3/bezier_motion.png)
- [局部观测和统一时钟语义](D:/yanjiu1/keyan1/docs/phase3_model.md)

- [阶段2验收与完整结果入口](D:/yanjiu1/keyan1/docs/phase2_acceptance.md)
- [连续动力学、前馈跟踪、同步语义与限制](D:/yanjiu1/keyan1/docs/phase2_model.md)
- [阶段0–1验收及完整文件清单](D:/yanjiu1/keyan1/docs/phase01_acceptance.md)
- [当前参数登记表](D:/yanjiu1/keyan1/docs/parameter_registry.csv)
- [论文对齐与补充假设](D:/yanjiu1/keyan1/docs/paper_alignment.md)
- [源码改编差异审计](D:/yanjiu1/keyan1/docs/source_adaptation_audit.md)
- [标注拓扑图](D:/yanjiu1/keyan1/results/phase1/topology.png)
- [SUMO实际瓶颈截图](D:/yanjiu1/keyan1/results/phase1/gui/sumo_bottleneck_zoom.png)

## 可视化演示入口

根目录 `runrun.py` 现在没有菜单。打开文件顶部“用户配置区”直接修改参数后，可以点击编辑器的“运行”或“调试”，也可以在 PowerShell 中执行 `python runrun.py`。程序会先生成一份新的 Phase5G 简单局部 if/else 编队轨迹；`SHOW_GUI = True` 时随后在 SUMO-GUI 中展示，`SHOW_GUI = False` 时只生成并校验轨迹。

顶部可编辑项包括车辆数、目标速度、随机种子、仿真时长、是否显示 GUI、播放延迟、自动缩放、播放结束等待，以及六项局部规则参数：局部观测范围、相邻车道期望间距、同车道/隔车道期望间距、位置容差、纵向加速度增量上限、每车最大编队换道次数。对应常量为 `VEHICLE_COUNT`、`TARGET_SPEED_MPS`、`RANDOM_SEED`、`SIMULATION_DURATION_S`、`SHOW_GUI`、`GUI_DELAY_MS`、`AUTO_ZOOM`、`WAIT_BEFORE_CLOSE`、`LOCAL_FORMATION_RANGE_M`、`ADJACENT_LANE_GAP_M`、`SAME_LANE_GAP_M`、`POSITION_TOLERANCE_M`、`FORMATION_ACCEL_LIMIT_MPS2` 和 `MAX_FORMATION_LANE_CHANGES`。

`python runrun.py --check` 只检查顶部配置、Phase5G入口、路网、`sumo-gui.exe` 与 TraCI 来源，不运行仿真、不创建演示目录，也不打开 GUI。

## Phase5G 最终复审整改（2026-09-15）

本轮没有改变已批准的无通信局部 if/else 控制动作或安全接受条件。五项整改已经落到可核验工程证据：分别保存 `longitudinal_guard` 与 `lane_guard` 并让公开 `guard` 指向当前被拒的换道守卫；直接入口使用有界输入公式，12车×45 s 的子进程预算为 `522 s`；`--check` 保持 `zero-write`；生成后处理与重放改为流式读取并绑定每次扫描的轨迹身份；Git archive 中补齐可运行闭包与便携 SUMO 发现。相关本地提交为 `29051ef`；`993998e`、`d562f12`、`3f1653a`、`b5934cc`、`193536a`、`37f4d37`；`9e6a65e`、`2f0a75c`、`a3ab69a`；`6af693a`、`4171067`、`ddb3d1c`、`ce66252`、`6ad5681`；以及根环境修复 `9dbb3af`。`6af693a` 首次新增76个闭包文件；后续整改后的最终精确闭包为96个文件，日志为 `D:\yanjiu1\keyan1\results\operations\20260915T061117194742Z_review-d2-final3-closure-audit_75fb2807`。其余逐文件范围和 RED/GREEN 日志见[阶段5检查点](D:/yanjiu1/keyan1/docs/phase5_checkpoint.md)。这些提交尚未 push。

工程事实：最终编译、simple 90/90、Phase5G 101/101、根 demo 75/75 均通过；根全回归在暴露空工具模板缺陷并补充 `research/common.py` 便携发现后为299/299。对应最终日志依次为 `D:\yanjiu1\keyan1\results\operations\20260915T063038691791Z_review-e-compile_c6968997`、`D:\yanjiu1\keyan1\results\operations\20260915T063047928512Z_review-e-simple-all_d1ab6c64`、`D:\yanjiu1\keyan1\results\operations\20260915T063245634168Z_review-e-phase5g-all_6985ebf9`、`D:\yanjiu1\keyan1\results\operations\20260915T063358991331Z_review-e-root-demo_cd6293b2` 和 `D:\yanjiu1\keyan1\results\operations\20260915T064347194380Z_review-e-root-regression-sumo-green_09bfdbb5`，均 exit 0、无 skip。`runrun.py --check` 的直接与原子前后审计为 `D:\yanjiu1\keyan1\results\operations\20260915T070343175313Z_review-e-runrun-check_30f050a0`、`D:\yanjiu1\keyan1\results\operations\20260915T070358941330Z_review-e-runrun-zero-write_115db1c6`，均 exit 0。内存中设置 `SHOW_GUI=False`、12车、45 s 的入口契约测试确认预算 `522 s`，并由真实加载器接受新建的12车/451帧可信测试夹具；它使用 mock subprocess，只验证入口而不是新增科学运行，日志为 `D:\yanjiu1\keyan1\results\operations\20260915T070439280777Z_review-e-runrun-debug-fixture_f2f56ede`。

新科学证据严格按3→6→12顺序各生成一次，固定 seed 1、10 m/s、45 s，输出基址为 `simple_final_review`；精确路径为 `D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\simple_final_review\20260915T064713884072Z_ee92fc0e`、`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\simple_final_review\20260915T064751667560Z_e3a1b27f`、`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\simple_final_review\20260915T065009813717Z_832d9ca2`。精确六车重放为 `D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\phase5g\replays\20260915T065716450367Z_8a58643e`，执行与语义重放通过且误差为0，但 `variant_acceptance_passed=false`。三组都没有碰撞，几何与舒适通过；也都没有形成全队编队、没有完成或编队换道、没有速度恢复。最终车道计数分别为 `[1,1,1]`、`[3,2,1]`、`[4,4,4]`，最低速度分别为8.3754383471、9.4966925096、8.0859588211 m/s；只有登记的六车门槛适用，30 s形成加10 s保持结果为 false。因此工程交付通过不等于科学验收通过，阶段6/7/8仍关闭。

六车轨迹流式审计记录2700个车辆决策。公开 `guard` 的非空计数为2250：换道拒绝451，纵向拒绝1342，纵向安全457；`lane_guard` 为451个换道拒绝，`longitudinal_guard` 为1792个拒绝和458个安全，原因分别为 `neighbor_reachable_occupancy` 与 `conditional_swept_prediction_clear`。全部非空项都有 `safe`、`reason`、`at_s`、`checked_s` 键；451个 `safety_rejected` 换道行的公开守卫均为被拒 `lane_guard`，不匹配数0。审计日志为 `D:\yanjiu1\keyan1\results\operations\20260915T070109830747Z_review-e-final-guard-audit_717c1287`。真实 `tracemalloc` 测得12车真实轨迹生成后处理峰值11.318586 MiB，真实六车精确重放峰值5.370682 MiB，均低于 `64 MiB`；没有用缩放推断替代测量。12车整包重放内存测量在3600 s超时，故没有12车重放峰值结论，该负日志及更早的测量脚本失败均保留在检查点。

旧 `simple_final` 三组负结果和所有早期失败包均保持不变；本轮不能据此声称形成成功、交通效率、通行能力或能耗收益。当前限制仍是相同的有限局部观测、每车私有记忆、每车最多一次换道和既有扫掠安全守卫，不允许通信、真实ID优先级、全局车辆数/槽位、中心分配、候选评分或障碍车。

## 运行

在 `D:\yanjiu1\keyan1` 的 PowerShell 中按下列顺序运行。使用当前Python解释器；SUMO主目录按 `SUMO_HOME`、非空 `configs/tools.json`、PATH 的顺序发现，并严格校验实际可执行文件与TraCI模块来源，空配置模板不会固定任何机器路径。

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
.\scripts\run.ps1 build
.\scripts\run.ps1 verify
.\scripts\run.ps1 environment
.\scripts\run.ps1 mcp
.\scripts\run.ps1 smoke
.\scripts\run.ps1 screenshot
.\scripts\run.ps1 test
.\scripts\run.ps1 phase2
.\scripts\run.ps1 phase2-replay
.\scripts\run.ps1 phase3
.\scripts\run.ps1 phase3-replay
.\scripts\run.ps1 phase4
.\scripts\run.ps1 phase4-replay
```

如系统脚本策略不允许，可直接调用解释器：

```powershell
python -I -B -S run.py verify
```

阶段4固定重放使用登记解释器执行 `run.py phase4-replay --run-dir results/phase4/runs/20260910T232224392627Z_ab0de887`；补充固定重放目录与交付核验命令见当前验收报告。新执行 `phase4` 会创建独立尝试，若普通驾驶门槛失败则按约定非零退出。阶段4日志、旧失败尝试、图和清单位于 `results/phase4/`；当前独立交付清单位于 `closure_20260911/delivery_manifest.json`，旧清单不回写。

其余子命令相同。`phase2`执行五个单车工况及步长细化，`phase2-replay`数值重放最近一次完整记录；指定历史运行可用 `python -I -B -S run.py phase2-replay --run-dir results/phase2/runs/<run_id>`。每次尝试独立建档，异常和门槛失败均保留，失败退出码非零。`-I -B -S`禁用环境搜索路径、字节码写入及`.pth`自动处理，入口仅显式加载项目和已登记依赖。已安装工具包版本见`requirements-tooling.txt`和`results/phase0/environment.json`，本轮没有安装或修改外部依赖。若将来必须安装，虚拟环境、缓存和临时文件也必须放在keyan1。

`build`只生成四档600 s需求，不运行实验矩阵。`smoke`只用1250 veh/(lane·h)的前60 s计划，加一个单独终止车道探针，并最多排空至240 s。各档CSV为共同到达计划；`.types.csv`是真实类型的离线初始化标签，不可进入邻车观测；`.rou.xml`为原生拓扑测试适配，不是NOA实现。所有方法后续必须复用相同需求文件。

运行日志保存在`results/phase0`、`results/phase1`与`results/phase2`；阶段2每次尝试在runs或replays下独立建档，最终验收引用固定run_id。冒烟重复运行前，旧目录会归档至`results/phase1/smoke_history`；当前结果先标记未完成，失败会留下明确状态与traceback；其他已知失败证据另存带`initial_failed`或`red`的文件。研究代码及配置有逐文件SHA-256记录，当前git分支为`phase01`；本轮已有本地提交，但尚未推送到远端。没有借用父目录测试基线。
