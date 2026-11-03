# F2：未来资源净空修订，等待交通与几何验收

候选源码：`tmp/staggered_bottleneck/candidates/midflow_future_resources_v2/native_rules.py`，SHA256 `d07c82501e3e86ce06529779b9c0bacd9469fd9654cc43c6dcd1c81bb21f8be4`。

相对独立F，仅把未来vacancy排除距离从matches±2改成已有CLEARANCE=8m；原F和S/V源均保留。相对S仍只变更`_fill`及其transform准备区调用，无V投影前车。

见[方法及反例](method.md)、[S→F2差异](native_rules.patch)、[F→F2差异](F_to_F2.patch)、[来源记录](source.json)、[构建脚本](build.py)、[验证记录](validation.json)。8项合同已通过，日志：`results/operations/20261103T105802157914Z_midflow-F2-green-contract_519dca16`。

测试命令（不启动SUMO）：

```powershell
$env:RULES_F='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\midflow_future_resources_v2\native_rules.py'
python -B -m unittest discover -s docs/experiments/2026-11-03-midflow-staggered/tests -p 'test_future*.py' -v
```

该源可交给runner作候选筛查；尚未运行交通、未被采纳，收益和24/45辆真实几何均未得到验证。未来几何指导选道，实际gap是闭环执行对象，不宣称指定future slot跟踪。
