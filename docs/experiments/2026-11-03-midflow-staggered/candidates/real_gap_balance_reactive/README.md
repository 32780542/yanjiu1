# DR：无未来占用预映射

源码`tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_reactive/native_rules.py`，422行，SHA `89a9299f0dd043600846f7e5d7239e68d079053a75e4d32e442f0619fbab6811`。

从D1仅删π映射一行；其余保持。[method.md](method.md)、[D1_to_DR.patch](D1_to_DR.patch)、[source.json](source.json)、[validation.json](validation.json)记录定义与证据。[build.py](build.py)验证父源并拒绝覆盖现有输出。

```powershell
$env:ABLATION_KIND='DR'
$env:RULES_ABLATION='D:/yanjiu1/keyan1/tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_reactive/native_rules.py'
python -B scripts/run_logged.py --label midflow-DR-contract --timeout 180 -- python -B docs/experiments/2026-11-03-midflow-staggered/tests/test_real_gap_balance_ablation.py -v
```

未改D1或生产，未运行交通。
