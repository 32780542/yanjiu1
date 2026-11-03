# DP：纵向相位关闭、保留横向组织

源码`tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_phase_off/native_rules.py`，423行，SHA `cfd2ee27031dac3b0efc2ef098551131878055b2518dfa4f9264a50886b4b86f`。

仅phase_speed置0，关系flag、未来资源及主动_fill保留，不添加普通超车，不称纯NOA。[method.md](method.md)、[D1_to_DP.patch](D1_to_DP.patch)、[source.json](source.json)与[validation.json](validation.json)记录定义和验证。[build.py](build.py)只读锁定D1源，拒绝覆盖。

```powershell
$env:ABLATION_KIND='DP'
$env:RULES_ABLATION='D:/yanjiu1/keyan1/tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_phase_off/native_rules.py'
python -B scripts/run_logged.py --label midflow-DP-contract --timeout 180 -- python -B docs/experiments/2026-11-03-midflow-staggered/tests/test_real_gap_balance_ablation.py -v
```

未改D1或生产，未运行交通。
