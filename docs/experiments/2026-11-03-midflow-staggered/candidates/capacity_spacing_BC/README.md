# BC：同容量参考、无主动交错组织

源码`tmp/staggered_bottleneck/candidates/midflow_capacity_spacing_control/native_rules.py`，429行，SHA256 `b25f0047ebe6b8989607bd9c7c94ce10e7579e495e300f00f7d7fda189889f35`。

锁定父B为`7d749ba8919efbf06efc0abd43846dee4c13b886e81019ae89c0f0116a1553d2`，只有`_following`和`_decide`改变。B的容量参考及90m真实邻道见证前车关联保留；BC关闭phase速度与自由补位，状态全0，并在transform提供普通NOA超车。必要合流、已有动作和真实gap执行保持。详见[method.md](method.md)。

[build.py](build.py)读取校验已锁B源，拒绝覆盖已有输出；测试oracle读取固定Git S blob及已锁B源，生产后续安装不改变基线。[B_to_BC.patch](B_to_BC.patch)、[source.json](source.json)与[validation.json](validation.json)记录差异、来源和验证。

```powershell
$env:RULES_BC='D:/yanjiu1/keyan1/tmp/staggered_bottleneck/candidates/midflow_capacity_spacing_control/native_rules.py'
python -B scripts/run_logged.py --label midflow-BC-contract --timeout 180 -- python -B docs/experiments/2026-11-03-midflow-staggered/tests/test_capacity_spacing_control.py -v
```

BC只作匹配非交错对照，不能标为原纯NOA。未运行交通，结果仍待独立筛查。
