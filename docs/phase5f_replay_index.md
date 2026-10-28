# 阶段5F正式运行与重放索引

本页相对路径均以 `D:/yanjiu1/keyan1` 为根。所有旧run、replay、失败尝试和比较目录保持只读；重新执行必须写新目录。

## 正式包

|用途|运行目录|运行wrapper|标准重放目录|重放wrapper|
|---|---|---|---|---|
|5C扩展，fixed同源对照|`variants/phase5f_adaptive_duration/results/phase5_r5/runs/20260913T162400640291Z_a5586029`|`.../results/operations/20260913T162400176188Z_phase5f_formal_extension_fixed_7d76a425`|`variants/phase5f_adaptive_duration/results/phase5_r5/replays/20260913T163527576957Z_4632477a`|`.../results/operations/20260913T163527149466Z_phase5f_replay_extension_fixed_5c2802b4`|
|5C扩展，adaptive_duration|`variants/phase5f_adaptive_duration/results/phase5_r5/runs/20260913T162400652574Z_9f6cc9d8`|`.../results/operations/20260913T162400185968Z_phase5f_formal_extension_adaptive_79a9db99`|`variants/phase5f_adaptive_duration/results/phase5_r5/replays/20260913T163527576957Z_6c53edf8`|`.../results/operations/20260913T163527149466Z_phase5f_replay_extension_adaptive_96085950`|
|原8案例17变体，adaptive_duration|`variants/phase5f_adaptive_duration/results/phase5_r5/runs/20260913T162400649059Z_207be322`|`.../results/operations/20260913T162400185968Z_phase5f_formal_original17_adaptive_2dc125ec`|`variants/phase5f_adaptive_duration/results/phase5_r5/replays/20260913T164250928637Z_74f0aa54`|`.../results/operations/20260913T164250585641Z_phase5f_replay_original17_adaptive_retry_118bdf0c`|

三份重放validation均 `passed=true`、errors/unstarted为空、source before/after相同。重放只证明封存记录可按同一源码和语义重建；它不把run中的失败前缀、碰撞、舒适失败或科学失败改写为通过。

## 精确复现命令

在 `D:/yanjiu1/keyan1/variants/phase5f_adaptive_duration` 下执行；每次会生成新目录：

```powershell
python -I -B -S scripts/run_logged.py --label phase5f_extension_fixed --timeout 1800 -- python -I -B -S run.py phase5-r5 --case-file phase5c_extension.json --waiting-policy fixed --lane-change-policy fixed
python -I -B -S scripts/run_logged.py --label phase5f_extension_adaptive_duration --timeout 1800 -- python -I -B -S run.py phase5-r5 --case-file phase5c_extension.json --waiting-policy fixed --lane-change-policy adaptive_duration
python -I -B -S scripts/run_logged.py --label phase5f_original_adaptive_duration --timeout 1800 -- python -I -B -S run.py phase5-r5 --case-file parent_frozen_r5_cases.json --waiting-policy fixed --lane-change-policy adaptive_duration
```

对某个已返回的精确run路径顺序执行重放：

```powershell
python -I -B -S scripts/run_logged.py --label phase5f_semantic_replay --timeout 1800 -- python -I -B -S run.py phase5-r5-replay --run-dir <exact-run-path>
```

不要并行启动使用同一 `results/phase5_r5/replays` 根的重放，因为 `latest.json.writing` 是共享操作指针。首次并行尝试的原17包PermissionError保留在 `variants/phase5f_adaptive_duration/results/operations/20260913T163527151469Z_phase5f_replay_original17_adaptive_8dfbec93`；正式顺序重放见上表。

## 比较与证据清单

最终比较目录为[comparison_formal_20260913T1659_final_v2](D:/yanjiu1/keyan1/results/phase5f/comparison_formal_20260913T1659_final_v2)，wrapper为 `results/operations/20260913T165832226824Z_phase5f_formal_comparison_final_v2_2c3ead81`，清单SHA256为 `17d799e9082bdd2b5b3a0fef27ca7bd191ea3e9fb6a39aee20016deeb0712c45`。

第一次比较器执行错误地要求原8案例包与扩展案例包的全部输入相同，忽略两者预登记的 `frozen_r5_cases.json` 本应不同，失败目录 `results/phase5f/comparison_formal_20260913T1649` 与wrapper `results/operations/20260913T165312841768Z_phase5f_formal_comparison_f367fecf` 原样保留。最终比较器要求扩展fixed/adaptive全输入相同、跨案例包仅冻结案例文件不同，其余协议输入相同；又加入11个非目标变体轨迹逐字兼容检查。

5E原始对照仍使用：

- run：`variants/phase5e_exact_endpoint/results/phase5_r5/runs/20260913T121814146616Z_12a1dc15`，manifest `8e6c6ffe4a94a0bb06c1f52ce50ae263dd4a84a017908667072cc63255e6ab3c`；
- replay：`variants/phase5e_exact_endpoint/results/phase5_r5/replays/20260913T122921286694Z_13a9cac5`，manifest `d1dee65f5b53363c79f4fe949e8d8fbf0e92bd9248f167699904fe6e6f05b2e8`。

科学解释与限制见[阶段5F验收](D:/yanjiu1/keyan1/docs/phase5f_adaptive_duration_acceptance.md)。
