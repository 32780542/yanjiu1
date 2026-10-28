# 阶段5D重放与失败记录索引

研究根 `D:/yanjiu1/keyan1`；新版本 `D:/yanjiu1/keyan1/variants/phase5d_local_game`。PY指 `C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe`。每次长命令由现有scripts/run_logged.py创建独立日志；不要覆盖旧attempt或把记录验收等同科学通过。

## 固定来源

- [前置核验](D:/yanjiu1/keyan1/results/phase5d/prerequisites_20260913T104302456188Z/verification.json)，wrapper `results/operations/20260913T104302289057Z_phase5d_readonly_parent_prerequisites_402e999b`。
- [隔离来源](D:/yanjiu1/keyan1/variants/phase5d_local_game/clone_provenance.json)，clone wrapper `results/operations/20260913T104421672817Z_phase5d_isolated_snapshot_ae418e41`。
- [预登记](D:/yanjiu1/keyan1/docs/phase5d_local_game_plan.md)、[113源码冻结](D:/yanjiu1/keyan1/variants/phase5d_local_game/phase5d_source_freeze.json)。初态沿用5C extension SHA `a21f8a4782955c4fab47ed91218b51f621f8a4d795b2d307b27f986aca4e682a`。
- [固定等待父包](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/phase5_r5/runs/20260913T062619294263Z_4126e0fd/validation.json)与[父标准重放](D:/yanjiu1/keyan1/variants/phase5c_lane_priority/results/phase5_r5/replays/20260913T063537973705Z_c407c3ee/validation.json)，沿用，不重跑。

## 两份正式运行与标准重放

|方法|正式包|标准重放目录|
|---|---|---|
|minimax|[run/validation](D:/yanjiu1/keyan1/variants/phase5d_local_game/results/phase5_r5/runs/20260913T111001467229Z_2d9c8d5f/validation.json)|[replay/validation](D:/yanjiu1/keyan1/variants/phase5d_local_game/results/phase5_r5/replays/20260913T112041226929Z_ba12ddc8/validation.json)|
|Stackelberg|[run/validation](D:/yanjiu1/keyan1/variants/phase5d_local_game/results/phase5_r5/runs/20260913T111103953169Z_c63ac16e/validation.json)|[replay/validation](D:/yanjiu1/keyan1/variants/phase5d_local_game/results/phase5_r5/replays/20260913T112236784168Z_4ee72d26/validation.json)|

正式wrapper位于variant/results/operations：

- `20260913T111001072685Z_phase5d_formal_minimax_f83f8262`，exit0/607.047s。
- `20260913T111103549825Z_phase5d_formal_stackelberg_retry_initialized_path_3b935a62`，exit0/607.687s。
- `20260913T112040750835Z_phase5d_minimax_semantic_replay_9dd95de8`，exit0/433.437s，6/6 passed。
- `20260913T112236370045Z_phase5d_stackelberg_semantic_replay_0e7d22d2`，exit0/437.812s，6/6 passed。两包来源前后相同，errors/unstarted为空；各1个OFF失败前缀仍failed。

复现正式实验在variant cwd（MODE=minimax或stackelberg，每次生成新目录）：

```text
PY -I -B -S scripts/run_logged.py --label phase5d_reproduce_MODE --timeout 1800 -- PY -I -B -S run.py phase5-r5 --case-file phase5c_extension.json --waiting-policy MODE
PY -I -B -S scripts/run_logged.py --label phase5d_replay_saved --timeout 1800 -- PY -I -B -S run.py phase5-r5-replay --run-dir ABSOLUTE_SAVED_RUN
```

不要从其他版本直接调用旧包；标准重放校验当前源码及输入与source snapshot相同。语义重放重建保存的策略、物理、自身记忆和SUMO回读/报告，不等于重新运行原生SUMO。每个OFF都保留26完整区间+失败尾；重放通过不会把它改成60s完成。

## 描述比较与异cwd快照重放

- [三来源比较](D:/yanjiu1/keyan1/results/phase5d/comparison_formal_20260913T1122/comparison.json)，wrapper root `results/operations/20260913T112236382062Z_phase5d_formal_three_policy_comparison_3ddc686b`，exit0/20.578s。
- [首次快照重放](D:/yanjiu1/keyan1/results/phase5d/comparison_snapshot_replay_20260913T1124/comparison.json)，wrapper `20260913T112420287164Z_phase5d_comparison_snapshot_replay_66b05811`，exit0/22.125s。实际子进程cwd仍D:/yanjiu1/keyan1，仅证明同目录重放；原跨目录声明被独立审查有效RED推翻，原结果不改。
- [首次字节核验](D:/yanjiu1/keyan1/results/phase5d/comparison_byte_verification_20260913T1125/verification.json)，wrapper `20260913T112536670955Z_phase5d_comparison_exact_snapshot_check_e2976fc7`，exit0/0.281s，字节确实一致，但不补足cwd条件。
- [实际异cwd摘要](D:/yanjiu1/keyan1/results/phase5d/comparison_actual_crosscwd_20260913T1132/comparison.json)，wrapper `20260913T113552974106Z_phase5d_actual_crosscwd_snapshot_886c702c`，exit0/20.734s。新[透明launcher及回执](D:/yanjiu1/keyan1/results/phase5d/crosscwd_receipt_20260913T1132/receipt.json)保存os.chdir后的实际D:/yanjiu1、命令与SHA；执行的仍是最初保存的摘要脚本。
- [实际异cwd整包核验](D:/yanjiu1/keyan1/results/phase5d/comparison_actual_crosscwd_bytes_20260913T1137/verification.json)，wrapper `20260913T113716843183Z_phase5d_actual_crosscwd_byte_check_35bdf005`，exit0/0.234s；文件集合及全部字节一致。最终绑定使用这组新摘要、回执与wrapper。

比较使用保存脚本及两个固定SHA的旧审查helper，只读原detector/记录，不调用在线policy。两描述包的`semantic_replays_bound=false`是创建时的范围说明；标准重放完成后最终交付另行绑定，不回写旧包。

```text
PY -I -B -S ABS_COMPARISON/script_snapshot.py --parent ABS_5C_RUN --minimax ABS_MINIMAX_RUN --stackelberg ABS_STACKELBERG_RUN --output NEW_OUTPUT
```

## 测试与工具失败

全部核心/控制器有效RED/GREEN位于variant/results/operations：

- 核心RED `20260913T105031201182Z_phase5d_core_red1_cc17b5b5`，13失败。
- 控制器RED `20260913T105537877386Z_phase5d_controller_red2_cd94ff79`，22项/7失败。
- 有限性RED `20260913T105834082279Z_phase5d_finite_red3_d277cfab`，27项/3失败。
- 最终核心GREEN `20260913T105912402119Z_phase5d_finite_green3_94378dc2`，27通过。
- harness RED `20260913T104703368097Z_phase5d_harness_red_8d1040ec`，6失败；初次GREEN尝试 `20260913T105616875799Z_phase5d_harness_green_9d0f3081`为测试夹具缺tmp目录错误；修夹具后 `20260913T105646652088Z_phase5d_harness_green_fixture_89398b9d`，6通过。
- game诊断严格类型/存在性RED `20260913T105809698434Z_phase5d_game_replay_types_red_85a80e74`，2断言失败；GREEN `20260913T105832553317Z_phase5d_game_replay_types_green_097ad4af`通过。

[完整347回归](D:/yanjiu1/keyan1/results/operations/20260913T110036350132Z_phase5d_integrated_regression_bound_e04df533/result.json)位于root/results/operations，exit0/279.921s。原脚本和成功freeze保留。回归helper在“有skip”时错误退出0的独立RED为`20260913T110707202509Z_phase5d_independent_evidence_red_cee72143`；新v2合成GREEN为`20260913T110900327210Z_phase5d_independent_evidence_v2_green_346424b3`。v2用于后续回归，输出独立attempts_v2/source_freeze_v2，不覆盖本轮原347/0skip证明；没有第二次347运行。

核心独审最终11通过：`20260913T111020045837Z_phase5d_independent_core_probes_f2a6c540`；首轮误写不存在探针路径 `20260913T110859020682Z_phase5d_independent_core_probes_bea7bb74`保留。证据独审及其探针工具误用错误、后续完整GREEN见[证据报告](D:/yanjiu1/keyan1/docs/phase5d_evidence_review.md)。

首次Stackelberg启动失败在variant wrapper `20260913T111001081269Z_phase5d_formal_stackelberg_6b5d70a2`，exit1/0.406s，未产生run包。原`output_path`收到`\\?\D:`扩展前缀形式后拒绝root包含关系；只复查路径并原样新试，没有弱化检查。此失败与原生SUMO车辆失败分列。

## 文献与初步检查

[原3篇26页全文审读证据](D:/yanjiu1/keyan1/results/phase5d/literature_20260913/review_verification.json)、[追加3篇原PDF归档](D:/yanjiu1/keyan1/results/phase5d/primary_archive_20260913T111008400597Z/manifest.json)和[七篇筛选](D:/yanjiu1/keyan1/docs/phase5d_game_theory_literature_review.md)。归档脚本与下载错误、PDF抽取警告保留。root最早三次归档环境尝试见operations中`phase5d_primary_paper_archive*`；成功归档wrapper `20260913T111006853716Z_phase5d_primary_literature_archive_21e71a8d`。

物理轨迹完整而外层核验未结束时的初步检查wrapper `20260913T111707970918Z_phase5d_provisional_completed_trace_inspection_33d85642`有明确provisional范围，不替代最终封存比较。
