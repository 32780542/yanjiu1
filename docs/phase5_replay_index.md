# 阶段5固定运行、重放与日志索引

本文件的相对路径全部以 `D:/yanjiu1/keyan1` 为根。源包包含实际初态、配置、源码与输入快照、逐步轨迹、判定和证据哈希；操作日志另保存精确命令、工作目录、解释器、stdout/stderr、退出码和外部超时。重新运行必须产生新目录，不覆盖下列旧包。研究科学判定与记录/重放判定分别见[主验收](D:/yanjiu1/keyan1/docs/phase5_completion_acceptance.md)。

## 已封存开发与选择

|方法|源码目录 / 固定源run|完整绑定重放目录（root/results/phase5 下）|
|---|---|---|
|A|根目录；`results/phase5/runs/20260912T180218593655Z_1e4080c3`|`comparison_20260912T191153232875Z_binding_6aec92e0`|
|B1|`variants/phase5_rules_front_first`；其下 `results/phase5/runs/20260912T185217115718Z_0bbe422c`|`comparison_20260912T200031670602Z_binding_15a2b3aa`|
|B2|`variants/phase5_rules_corner_first`；其下 `results/phase5/runs/20260912T185217113215Z_3a3b35df`|`comparison_20260912T200259973699Z_binding_4446e653`|

三包各21个登记变体，所有绑定及随后来源复核通过。选择只使用六个开发随机case，按预登记 whole → C → B1平局顺序执行，正式选择记录为[selection.json](D:/yanjiu1/keyan1/results/phase5/comparison_20260912T210839292741Z_selection_652993c7/selection.json)。B1因平均C的有限差异被选中，这不等于保留集胜出。

## 已封存保留集

|方法|固定源run|绑定重放目录（root/results/phase5 下）|
|---|---|---|
|A|`variants/phase5_cost_holdout/results/phase5/runs/20260912T211254802638Z_b9c31d10`|`comparison_20260912T221225440029Z_binding_a5fd1653`|
|B1|`variants/phase5_rules_front_first_holdout/results/phase5/runs/20260912T211254789627Z_3d1257fa`|`comparison_20260912T221045541952Z_binding_26b7acbc`|

各13变体：六种子OFF/ON与首例半控制周期。两绑定及最后一次来源核验均通过；原包 subset complete_suite=false不作为实验崩溃解释。[固定配对记录](D:/yanjiu1/keyan1/results/phase5/comparison_20260912T230631758620Z_heldout_47117b4d/heldout.json)确认重复OFF完整轨迹一致，已合并为18个主要单元，独立样本量仍是六种子。A/B1/OFF均全队0/6、局部2/6；B1平均C低于A，A/B1均低于OFF。该报告SHA256为 `c4a9d6b11429c69673d26b6bdea7b1f6d8cdaf76db19dd93d8cc00d627f3e326`，封存清单SHA为 `0b891a1ad0516b57640f7d155d7a18c6082e64fface7512719a34ea7b40d923a`。

A标准replay位于其副本 `results/phase5/replays/20260912T221228394230Z_8afb9b96`，validation SHA `83fb197650611b5806cc2c90e1d72835b2603c4d09309cd33212ec37c415a43f`；B1为其副本 `results/phase5/replays/20260912T221048306395Z_e4fc5f51`，validation SHA `ea5b28b8889ff283cd160074142ff1ad9cc2689431508054b5fd87ed0df63bdd`。A/B1最终来源核验日志分别是root `results/operations/20260912T230612530705Z_phase5_cost_heldout_binding_final_verification_7411b2fa` / `20260912T230424706781Z_phase5_selected_front_heldout_binding_final_verification_4b3a6864`；固定配对汇总日志 `20260912T230631571676Z_phase5_formal_heldout_paired_summary_6f25d9ef`，57.859s退出0。

冻结工具位于 `tmp/phase5_comparison_design`：`phase5_bind_v1.py` SHA256 `622991c1e5a4aa66f1270120ffc5eceb87f7ebed590cc4a8ad4be1bab8f3cae2`、`phase5_select_v1.py` `f2da6e517f3e6be61a0b0c08ac106c931360fa52b69896343282d37c09a7af1c`、`phase5_heldout_v1.py` `f80314e9b0334ead62b2511bfe017c74696b95263a7e6724fbed883a44c4e4d0`。固定v1入口不使用其后编辑的开发脚本。

原绑定完成后，可只核验已有绑定而不再启动车辆或整包重放。例如从研究根目录执行：

```powershell
& 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' scripts/run_logged.py --label phase5_existing_A_binding_check --timeout 600 -- 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -I -B -S tmp/phase5_comparison_design/phase5_bind_v1.py --workspace 'D:/yanjiu1/keyan1' verify-binding --binding-dir 'D:/yanjiu1/keyan1/results/phase5/comparison_20260912T221225440029Z_binding_a5fd1653'
```

## R5完整新版本

源码在 `variants/phase5_r5_completed`，与旧比较版本分开。106源码、整合来源、初态冻结、267项回归与审查入口列在主验收报告；旧开发/保留结果不能冒充新R5版本的编队验证。

- [正式初态](D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/initials/frozen_cases.json)，完整8场景仅一次封存，不重新筛选或抽样。
- [正式17变体运行](D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/runs/20260912T222655136582Z_203b85c8/validation.json)：11完整、6失败前缀、0未启动；记录通过、驾驶失败保留。
- [八案例报告与描述性摘要](D:/yanjiu1/keyan1/docs/phase5_r5_formal_mechanism_summary.md)：等待、提交、实际换道、低速门槛、再入未覆盖和失败判据分别呈现；主摘要和独立0.005s附录均完成异cwd字节核验。
- [专用标准重放](D:/yanjiu1/keyan1/variants/phase5_r5_completed/results/phase5_r5/replays/20260912T223428312609Z_75c18330/validation.json)：17案例通过，errors为空，源码/输入/全部私有记忆链一致，原工程与驾驶失败仍为false。
- 实际运行/重放日志分别在该副本 `results/operations/20260912T222654796674Z_phase5_r5_formal_mechanism_suite_595af2b3` 与 `20260912T223427979958Z_phase5_r5_formal_semantic_replay_3e602177`，耗时429.625s / 303.781s，均正常退出。

R5重放的完整可复制命令见[正确版本与下一入口](D:/yanjiu1/keyan1/docs/phase5_next_entry.md)。R5输出使用其专用clock/private schema，不能调用旧A/B绑定脚本来代替。

## 辅助证据

- [阶段4前置复核](D:/yanjiu1/keyan1/docs/phase5_prerequisite_review_20260913.md)：读取实际代码和原验收，固定测试及普通/采样重放通过。
- [开发运动摘要](D:/yanjiu1/keyan1/docs/phase5_motion_summary.md)与[保留集运动摘要](D:/yanjiu1/keyan1/docs/phase5_heldout_motion_summary.md)：实际速度、停车、加速度/jerk及raw覆盖；脚本快照异cwd重放字节一致。
- [对称反例](D:/yanjiu1/keyan1/docs/phase5_symmetry_review.md)：45s完全并排、无前参考的OFF/A/B1/B2均未形成，不加入随机分母。
- [守卫诊断](D:/yanjiu1/keyan1/docs/phase5_guard_diagnostics.md)：拒绝原因和分母，不把拒绝率降低解释为安全或形成提升。
- [需求矩阵](D:/yanjiu1/keyan1/docs/phase5_requirement_traceability.md)与[检查点](D:/yanjiu1/keyan1/docs/phase5_checkpoint.md)：实现、失败、参数变化、历史RED及后续入口。

实验失败、单元开发RED、历史依赖缺失、审查中构造的坏包和传输中断分别记录。传输恢复不算研究通过，重放通过也不更改失败的实验结论。
