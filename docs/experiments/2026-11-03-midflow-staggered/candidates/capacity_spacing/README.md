# B：capacity spacing

独立来源：冻结S `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`。

候选源码：`tmp/staggered_bottleneck/candidates/midflow_capacity_spacing/native_rules.py`，468行，SHA256 `7d749ba8919efbf06efc0abd43846dee4c13b886e81019ae89c0f0116a1553d2`。

在缩道地图transform上游，将组织参考30/15m按车道资源比3/2改为45/22.5m。640m起恢复原尺度；实际车相位始终根据其自身位置。8m clear、安全帽、公开NOA CF预测和真实gap执行原样。详见[method.md](method.md)。

构建器[build.py](build.py)只读固定Git提交`1aa86344af2a269053cd4fcda9d58168697daf17`的S blob并校验其哈希，再写新候选；现有输出存在时拒绝覆盖。测试oracle也读固定blob，因此后续生产安装不改变比较基线。[native_rules.patch](native_rules.patch)为S→B差异，[source.json](source.json)记录来源及哈希。[validation.json](validation.json)为独立静态合同日志索引。

PowerShell复核（不运行交通）：

```powershell
$env:RULES_B='D:/yanjiu1/keyan1/tmp/staggered_bottleneck/candidates/midflow_capacity_spacing/native_rules.py'
python -B scripts/run_logged.py --label midflow-B-contract --timeout 180 -- python -B docs/experiments/2026-11-03-midflow-staggered/tests/test_capacity_spacing.py -v
```

没有修改生产、旧候选或Git状态，也没有运行交通。密度匹配是巡航参考的设计理由；暂不构成流量收益证据。
