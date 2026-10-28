# 阶段5B固定证据与重放入口

工作副本为 `D:/yanjiu1/keyan1/variants/phase5b_conservative_release`。根目录run.py仍是旧A入口。本单元保留父R5与新规则两份独立版本，不能互换源码去重放对方的记录。

|证据|固定路径|
|---|---|
|父版本正式包|[validation.json](D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/runs/20260912T222655136582Z_203b85c8/validation.json)|
|父版本正式语义重放|[validation.json](D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/replays/20260912T223428312609Z_75c18330/validation.json)|
|新版本源码/输入冻结|[phase5b_source_freeze.json](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/phase5b_source_freeze.json)|
|新正式17变体|[validation.json](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/results/phase5_r5/runs/20260913T042930121115Z_deb427af/validation.json)|
|新原生命令/退出/日志|[result.json](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/results/operations/20260913T042929716765Z_phase5b_formal_mechanism_suite_05b34a2f/result.json)|
|固定两版本比较|[comparison.json](D:/yanjiu1/keyan1/results/phase5b/comparison_formal_20260913T0444/comparison.json)|
|全部34描述行|[rows.json](D:/yanjiu1/keyan1/results/phase5b/descriptive_rows_20260913T0446/rows.json)|
|新标准语义重放|[validation.json](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/results/phase5_r5/replays/20260913T044401892589Z_bd809c6b/validation.json)|
|活跃竞争保存动作细化|[validation.json](D:/yanjiu1/keyan1/variants/phase5b_conservative_release/results/phase5b/active_integration_20260913T0455/validation.json)|
|该细化的独立快照重放|[result.json](D:/yanjiu1/keyan1/results/operations/20260913T045527454997Z_phase5b_active_refinement_snapshot_replay_correct_source_1caae3a4/result.json)|

新标准重放17/17通过，3失败前缀仍保留原失败判定；活跃细化4车及独立快照重放通过。新run证据manifest SHA256为`6f7ddd2a844f9b58a29bd7efd7b7774d9d3bad5e94809c5f99e72784b51ff192`，比较包manifest为`c1b4476848251b2c59abd8912bd22d4557ff75b649e8f6e45aa62b73c696b00f`。

## 标准语义重放

以下命令使用封存的初态、完整本车私有状态与原始记录，不重抽。每次输出新目录，并记录命令、stdout/stderr、退出码和超时。检查源码/输入/证据集合后，逐帧重建动作、物理状态、记忆和抽样链，同时保留已失败的物理前缀。

```powershell
Set-Location -LiteralPath 'D:/yanjiu1/keyan1/variants/phase5b_conservative_release'
& 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' scripts/run_logged.py --label phase5b_recorded_replay --timeout 7200 -- 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -I -B -S run.py phase5-r5-replay --run-dir 'D:/yanjiu1/keyan1/variants/phase5b_conservative_release/results/phase5_r5/runs/20260913T042930121115Z_deb427af'
```

该重放重建控制/物理并审计捕获的SUMO读回，不是独立再次运行SUMO来证明原生碰撞语义。旧包的6失败和新包的3失败前缀分别属于各自保存窗口；短前缀之后不补零、不外推，也不生成全窗口差值。

## 描述性比较重放

比较器只读封存包，严格核对固定父manifest、106→107源码范围、唯一新增计划输入、8个物理/私有初态、17变体参数，以及OFF共同前缀的动作/记忆/物理链。ON仅在双方完整时生成全窗口差值。它的`semantic_replays_bound=false`是自身作用范围；最终交付包另行连接两侧标准重放，不修改比较原件。

```powershell
Set-Location -LiteralPath 'D:/yanjiu1/keyan1'
$phase5bReplayOut = Join-Path 'D:/yanjiu1/keyan1/results/phase5b' ('comparison_replay_' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ'))
& 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' scripts/run_logged.py --label phase5b_comparison_snapshot_replay --timeout 600 -- 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -I -B -S 'D:/yanjiu1/keyan1/results/phase5b/comparison_formal_20260913T0444/script_snapshot.py' --parent-run 'D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/runs/20260912T222655136582Z_203b85c8' --new-run 'D:/yanjiu1/keyan1/variants/phase5b_conservative_release/results/phase5_r5/runs/20260913T042930121115Z_deb427af' --output-dir $phase5bReplayOut
```

预登记与诊断见[规则计划](D:/yanjiu1/keyan1/docs/phase5b_conservative_release_plan.md)、[R5诊断](D:/yanjiu1/keyan1/docs/phase5b_r5_diagnosis.md)、[SUMO诊断](D:/yanjiu1/keyan1/docs/phase5b_sumo_diagnosis.md)。未通过的科学条件见[本单元验收](D:/yanjiu1/keyan1/docs/phase5b_conservative_release_acceptance.md)。

## 活跃竞争积分快照重放

只重建保存动作下的4车0.005 s积分记录，不执行控制策略或原生SUMO。packet位于新副本内，满足原输出边界；不得用放宽输出检查的办法重用早期错误目录。

```powershell
Set-Location -LiteralPath 'D:/yanjiu1/keyan1'
& 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' scripts/run_logged.py --label phase5b_active_snapshot_replay --timeout 600 -- 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -I -B -S 'D:/yanjiu1/keyan1/variants/phase5b_conservative_release/results/phase5b/active_integration_20260913T0455/script_snapshot.py' replay --workspace 'D:/yanjiu1/keyan1/variants/phase5b_conservative_release' --source-run 'D:/yanjiu1/keyan1/variants/phase5b_conservative_release/results/phase5_r5/runs/20260913T042930121115Z_deb427af' --packet 'D:/yanjiu1/keyan1/variants/phase5b_conservative_release/results/phase5b/active_integration_20260913T0455' --expected-manifest-sha ee1900be432a7fa90a42d59c56bebc5d70d686dda72b1ceaf818fd27e09185ed
```

两次错误调用日志以及未封存的部分补充输出单独保留，不能替代上述正式packet；失败原因和固定路径见验收报告“保留的执行错误”。
