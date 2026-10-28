# 阶段5E重放与失败日志索引

研究根为 `D:/yanjiu1/keyan1`，阶段5E版本为 `D:/yanjiu1/keyan1/variants/phase5e_exact_endpoint`。`PY`指 `C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe`。所有旧目录只读；重试必须产生新目录。

## 前置、隔离与TDD

- 前置核验首次工具失败：`results/operations/20260913T120254804556Z_phase5e_parent_prerequisites_5955dd32`，exit1；原因是核验脚本误排除嵌套同名清单，正式证据无损。
- 修正后前置核验：`results/operations/20260913T120339645205Z_phase5e_parent_prerequisites_retry_7444c465`，exit0/0.266 s；[verification](D:/yanjiu1/keyan1/results/phase5e/prerequisites_20260913T120339903006Z_27c44d80/verification.json)。
- 隔离克隆：`results/operations/20260913T120400799108Z_phase5e_isolated_snapshot_d3257bed`，exit0/1.156 s；[provenance](D:/yanjiu1/keyan1/variants/phase5e_exact_endpoint/clone_provenance.json)。
- 端点RED/GREEN：variant operations中的 `20260913T120439300056Z_phase5e_endpoint_red_f5ac11c9`（exit1/0.453 s）与 `20260913T120514456003Z_phase5e_endpoint_green_12422283`（exit0/0.437 s）。
- 计划输入RED/GREEN：`20260913T120533040109Z_phase5e_input_binding_red_6050ebca`（exit1/0.437 s）与 `20260913T120600153039Z_phase5e_input_binding_green_8390e31f`（exit0/0.484 s）。
- 受影响回归首次有效失败：root operations `20260913T120711258708Z_phase5e_affected_regression_0a3bf86b`，exit1/162.172 s；40个tmp夹具错误与5个预期兼容断言失败，源码未变。
- 最终受影响回归：root operations `20260913T121118654980Z_phase5e_affected_regression_retry_72f5c23e`，exit0/389.766 s；191通过、0失败/错误/跳过、源码未变。[冻结](D:/yanjiu1/keyan1/variants/phase5e_exact_endpoint/phase5e_source_freeze.json)。

## 正式运行与标准重放

在5E variant cwd复现会创建新目录：

```text
PY -I -B -S scripts/run_logged.py --label phase5e_reproduce --timeout 1800 -- PY -I -B -S run.py phase5-r5 --case-file parent_frozen_r5_cases.json --waiting-policy fixed
PY -I -B -S scripts/run_logged.py --label phase5e_replay_saved --timeout 1800 -- PY -I -B -S run.py phase5-r5-replay --run-dir ABSOLUTE_SAVED_RUN
```

- 正式run：[validation](D:/yanjiu1/keyan1/variants/phase5e_exact_endpoint/results/phase5_r5/runs/20260913T121814146616Z_12a1dc15/validation.json)，wrapper `variants/phase5e_exact_endpoint/results/operations/20260913T121813751610Z_phase5e_formal_exact_endpoint_f9b5e2ac`，exit0/623.437 s。17/17启动/封存、13完整、4 OFF失败前缀、记录通过、驾驶/工程false、source变化空。manifest SHA `8e6c6ffe4a94a0bb06c1f52ce50ae263dd4a84a017908667072cc63255e6ab3c`。
- 标准replay：[validation](D:/yanjiu1/keyan1/variants/phase5e_exact_endpoint/results/phase5_r5/replays/20260913T122921286694Z_13a9cac5/validation.json)，wrapper `variants/phase5e_exact_endpoint/results/operations/20260913T122920952590Z_phase5e_exact_endpoint_semantic_replay_1dcdd357`，exit0/336.484 s。17项passed、errors/unstarted空、source before=after。manifest SHA `d1dee65f5b53363c79f4fe949e8d8fbf0e92bd9248f167699904fe6e6f05b2e8`。

4个失败前缀为 `r5_competing_r5_off`、`r5_speed_floor_r5_off`、`r5_same_private_state_r5_off`、`r5_quantized_private_states_r5_off`。新增speed-floor OFF失败在2.8 s原生碰撞，保存26个完整控制区间与第27个失败记录；不得扩展为30 s全窗。

## 固定比较

- 首次比较：`results/phase5e/comparison_20260913T1237_exact_endpoint`，通过，但未在case摘要中展开原始error/warnings；保留不用作最终入口。
- 最终比较：[comparison](D:/yanjiu1/keyan1/results/phase5e/comparison_20260913T1244_exact_endpoint_final/comparison.json)，wrapper `results/operations/20260913T124206648022Z_phase5e_formal_parent_comparison_final_e8cd51ab`，exit0/6.531 s。绑定父/新run与父/新标准replay，17变体、同案例/参数/初态，端点与不可行分支探针通过；5文件集合/哈希精确，manifest SHA `01a6904fb556226a399d770359028d13dd17e2d116f6bb2ce68d468a4542ce79`。

比较脚本是只读数据审查，不调用在线策略选择车辆。父到新源码还包含阶段5D已经单独验收的inactive fixed-mode兼容层；191项回归另验证5E默认/fixed一致，并把相对5C的行为差限制在端点分支。比较重放成功不表示科学验收通过。

## 约束

复现不得修改manifest、案例、源码或旧失败目录；不得重抽私有状态、挑选窗口/seed或压制SUMO碰撞。只允许本车、有限局部观测和自身记忆；禁止隐含通信、车型真值、真实ID优先、邻车私有意图、全局槽位与中心调度补救。

