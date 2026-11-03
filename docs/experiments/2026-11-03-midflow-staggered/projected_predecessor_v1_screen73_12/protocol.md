# V1对S短筛查：73/74，12例

2026-11-03 18:32（Asia/Shanghai）在本批结果前登记。root授权本批作为局部投影前车V1的短期方法筛查，基线24例继续2并发，本批仅1并发，合计3个模拟；不使用91–93最终种子。

S为当前生产锁源 `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`（461行）。V1规则为 `tmp/staggered_bottleneck/candidates/midflow_projected_predecessor_v1/native_rules.py`，SHA256 `517d169ff012950e288c20a9fca9225db20bae6ffcc1a6f3aca43c05c8790c7d`（470行）。实现与独立局部状态合同由root负责，方法记录见 `candidates/projected_predecessor`。仅替换规则；其余九源与原runner固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787` 相同。生产、旧工具、入口、安全和NOA容量不改。

每上游车道1500、1750、2000辆/h，种子73/74，lane_drop（3→2）道路，transform模式，S/V两规则，共12例、6个V减S同输入配对。180秒持续Bernoulli请求、统一500秒物理上限；原0.1秒步长、1秒变道、巡航28.8、最高33.3m/s保持。每case完整结束后才评价，墙钟不当作物理交通表现；未完成、碰撞、无改善、执行失败均保留。

```powershell
python -B scripts/run_logged.py --label midflow-V1-screen73-12 --timeout 5400 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate S=variants/phase5g_pure_formation/noa/native_rules.py V=tmp/staggered_bottleneck/candidates/midflow_projected_predecessor_v1/native_rules.py --stage midflow_V1_screen73 --flows 1500 1750 2000 --seeds 73 74 --scenarios lane_drop --modes transform --duration 180 --max-time 500 --jobs 1 --worker-timeout 1200 --output tmp/staggered_bottleneck/20261103_midflow_V1_screen73_12
```

新raw目录独占，不重用旧尝试。逐例run_logged、compact/ledger/originals/离线验封直接复用原runner。先完整保留所有raw，待机制agent提取后，至少保留seed73的三流量S/V六例positions/events；其余成功case在完整封包和离线复核后才精确清理两大轨迹，失败raw保持。

```powershell
python -B scripts/run_logged.py --label midflow-V1-screen73-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_V1_screen73_12 --reference S --output docs/experiments/2026-11-03-midflow-staggered/projected_predecessor_v1_screen73_12/analysis
```

此分析的有效比较只取`V-minus-S_transform`：同mode transform，V减S，**不是V减NOA**。原summarize还会列出6个缺失S/noa的策略配对，保持可见但不得引用其性能。主指标完整请求系统时间，并列行程、入口等待、燃油、640–1100米段、变道及原0/1几何证据。180秒需求未覆盖原[100,600)完整窗口，因此原工具的固定窗口formal指标为空，不能补值、伪称完整窗口或容量。

后续候选不得改写本批身份、规则SHA、输入或评价；Git由root统一处理。
