# GP2：CTH-compatible admission within bound real gap

候选源码：`tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_v2/native_rules.py`，523行，SHA256 `37306e86a8e0e1045763bf54ebb3adca60ebc489dde6925a61553240ad0195cc`。

相对冻结GP只改`_gap_plan`和`_gap_clear`，增加machine `ulp`导入。原GP、S/V/F/C5源均未修改。见[方法及边界](method.md)、[GP→GP2差异](GP_to_GP2.patch)、[构建脚本](build.py)、[来源](source.json)、[验证索引](validation.json)及[开发窗口账本](development_witnesses.json)。

9项admission/scope合同全绿，另1600个名义状态的cubic加速度、精确速度极值及道路界核对通过。没有运行交通仿真或修改生产；该源可交独立runner筛查，尚无收益、真实几何或全局稳定保证。

```powershell
$env:RULES_GP2='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\midflow_bound_real_gap_v2\native_rules.py'
python -B docs/experiments/2026-11-03-midflow-staggered/tests/test_bound_real_gap_admission.py -v
```
