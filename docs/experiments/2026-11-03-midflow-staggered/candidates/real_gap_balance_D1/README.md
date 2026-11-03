# D1：排除自身的真实gap选择

源码`tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py`，423行，SHA256 `2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a`。

父D0保持冻结。一行评分邻车API排除候选自身，修复横向偏心车辆可能污染目标gap的问题；其余策略、阈值、实际动作与安全层不变。[method.md](method.md)给出同帧目标/执行绑定条件及10000状态审计范围。

[build.py](build.py)、[D0_to_D1.patch](D0_to_D1.patch)、[source.json](source.json)及[validation.json](validation.json)记录来源和合同。[D0_D1_10000_comparison.json](D0_D1_10000_comparison.json)保留差异样本。

```powershell
$env:RULES_D='D:/yanjiu1/keyan1/tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py'
python -B scripts/run_logged.py --label midflow-D1-contract --timeout 180 -- python -B docs/experiments/2026-11-03-midflow-staggered/tests/test_real_gap_balance.py -v
$env:RULES_D_SELF=$env:RULES_D
python -B scripts/run_logged.py --label midflow-D1-self --timeout 180 -- python -B docs/experiments/2026-11-03-midflow-staggered/tests/test_real_gap_balance_self_exclusion.py -v
```

未修改生产、旧候选或Git状态，未运行交通。不能将D0与D1交通记录混为同一源。
