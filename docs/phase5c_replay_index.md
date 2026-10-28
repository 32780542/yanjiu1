# 阶段5C重放与失败保留索引

当前源码为[独立5C副本](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/run.py)，110项，冻结记录见[成功source freeze](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/phase5c_source_freeze.json)。根目录原A实现与5B源码均未替换。以下为本轮新输出；所有旧尝试只读。

## 正式运行与标准语义重放

|内容|固定输出|原始运行日志|
|---|---|---|
|原8案例17变体|[run validation](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/phase5_r5/runs/20260913T061451357664Z_cd3da24b/validation.json)|[wrapper](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/operations/20260913T061451110885Z_phase5c_formal_original_mechanisms_1407fe0a/result.json)|
|对应17项标准重放|[replay validation](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/phase5_r5/replays/20260913T062619302264Z_135ea687/validation.json)|[wrapper](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/operations/20260913T062619017260Z_phase5c_original_semantic_replay_d3192948/result.json)|
|新扩展6变体|[run validation](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/phase5_r5/runs/20260913T062619294263Z_4126e0fd/validation.json)|[wrapper](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/operations/20260913T062619009264Z_phase5c_formal_gradual_extension_4f341559/result.json)|
|对应6项标准重放|[replay validation](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/phase5_r5/replays/20260913T063537973705Z_c407c3ee/validation.json)|[wrapper](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/operations/20260913T063537672656Z_phase5c_gradual_semantic_replay_8e5d2fca/result.json)|

原17包evidence manifest SHA256：`3155cca5eaa634ead59353a6327a244ae70730f1fa4ee18f4f6bd9d75c37ff34`（339文件）；扩展包：`08e1ab0f619dd404fd048d62c3718838224c55d4fbcbaf14d9939be76ae03f5c`（207文件）。源包各含完整code/input_snapshot、控制输入/动作/自身记忆、物理子步、原生SUMO回读/警告、case index、评估及失败前缀。

原17包有3个OFF失败前缀，扩展有1个三车OFF失败前缀，均保留。原front_priority OFF虽完整执行，驾驶/舒适仍失败。标准重放重建控制器、私有链、模型子步和保存的SUMO报告，并非再次启动原生SUMO；重放通过不抹去源实验失败。

在PowerShell重新执行标准重放，输出会创建新目录：

```powershell
Set-Location D:/yanjiu1/keyan1/variants/phase5c_lane_priority
& C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe -I -B -S scripts/run_logged.py --label phase5c_replay_original --timeout 7200 -- C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe -I -B -S run.py phase5-r5-replay --run-dir D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/phase5_r5/runs/20260913T061451357664Z_cd3da24b
& C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe -I -B -S scripts/run_logged.py --label phase5c_replay_gradual --timeout 7200 -- C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe -I -B -S run.py phase5-r5-replay --run-dir D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/phase5_r5/runs/20260913T062619294263Z_4126e0fd
```

当前源码或输入改变时应拒绝重放，不得删改manifest绕过。实际车辆重跑使用同副本的 `run.py phase5-r5 --case-file`，案例路径分别为 `D:/yanjiu1/keyan1/variants/phase5c_lane_priority/frozen_r5_cases.json` 和 `D:/yanjiu1/keyan1/variants/phase5c_lane_priority/phase5c_extension.json`；仍需run_logged和新输出。不得重新冻结或重抽私有初态。

## 描述性比较与数据脚本重放

- [父/新比较](D:/yanjiu1/keyan1/results/phase5c/comparison_formal_20260913T0626/comparison.json)，[正式日志](D:/yanjiu1/keyan1/results/operations/20260913T062642370273Z_phase5c_formal_parent_comparison_a4f8d835/result.json)，[异cwd保存脚本重放](D:/yanjiu1/keyan1/results/operations/20260913T062803254714Z_phase5c_comparison_snapshot_replay_6c97c1d0/result.json)，[整包文件集合/字节一致](D:/yanjiu1/keyan1/results/phase5c/comparison_byte_verification_20260913T0632/verification.json)。14对完整窗有描述差值，3对含失败前缀的全窗差值为null。
- [34行原值](D:/yanjiu1/keyan1/results/phase5c/descriptive_rows_20260913T0628/rows.json)，[日志](D:/yanjiu1/keyan1/results/operations/20260913T062803283226Z_phase5c_descriptive_fixed_rows_b26c14a4/result.json)。复用此前已审只读行提取器，无控制器调用。
- [三车逐拍生命周期/原检测](D:/yanjiu1/keyan1/results/phase5c/gradual_summary_20260913T0636/summary.json)，[正式日志](D:/yanjiu1/keyan1/results/operations/20260913T063537672656Z_phase5c_gradual_trace_summary_d5f9414e/result.json)，[异cwd重放](D:/yanjiu1/keyan1/results/operations/20260913T063751018827Z_phase5c_gradual_summary_snapshot_replay_be9f714b/result.json)，[整包字节一致](D:/yanjiu1/keyan1/results/phase5c/gradual_byte_verification_20260913T0638/verification.json)。三受控车子集与全5物理actor分开，检测器源码锁定父版。

两个摘要目录均保存 `script_snapshot.py` 及依赖。父/新重放命令接收 `--parent-run <上述5B固定run> --new-run <上述5C原17run> --output-dir <全新目录>`；三车摘要命令接收 `--run <上述扩展run> --output <全新目录>`。均为只读数据分析，其语义重放绑定由最终交付另外完成。

## 前置、回归与修复证据

[前置核验](D:/yanjiu1/keyan1/results/phase5c/prerequisites_20260913T053649949076Z/verification.json)、[父5B验收](D:/yanjiu1/keyan1/docs/phase5b_conservative_release_acceptance.md)、[5C计划](D:/yanjiu1/keyan1/docs/phase5c_lane_priority_plan.md)、[313回归日志](D:/yanjiu1/keyan1/results/operations/20260913T061008877499Z_phase5c_integrated_regression_bound_885174e7/result.json)、[单次扩展冻结](D:/yanjiu1/keyan1/results/operations/20260913T061438776913Z_phase5c_freeze_registered_extension_710e1ae3/result.json)。

首轮完整回归的1项失败在[原日志](D:/yanjiu1/keyan1/results/operations/20260913T060409792208Z_phase5c_integrated_regression_ade9712e/result.json)中保留。核心初次道路夹具错误、有效RED、guard夹具修正、三个旧draw夹具RED/GREEN，以及实验测试的并发源码变化拒绝，均见[核心审查](D:/yanjiu1/keyan1/docs/phase5c_independent_review.md)和副本results/operations独立日志；没有改写旧尝试。

[证据审查](D:/yanjiu1/keyan1/docs/phase5c_evidence_review.md)记录3个已修P2及14项独立GREEN。回归首行绑定完整attempt source freeze的哈希及保存脚本，最终绑定不能用另一版源码的同数量测试日志替代。

最终收口使用[root绑定脚本](D:/yanjiu1/keyan1/tmp/phase5c_save_acceptance.py)和[显式路径spec](D:/yanjiu1/keyan1/tmp/phase5c_delivery_inputs.json)，检查两侧源包、三个标准重放（含5B父包）、当前110源码/输入、完整回归来源、比较与三车摘要，再保存新acceptance和报告快照。以实际acceptance结果为准，不从运行进度推断完成。
