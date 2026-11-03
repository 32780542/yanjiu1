# 三档1800秒持续需求公共NOA参考：81/82，6例

2026-11-03 18:54（Asia/Shanghai）在本批结果前登记，按root授权于600秒基线24例结束后启动。每上游车道仅1500、1750、2000辆/h，种子81/82，lane_drop（3→2），noa模式，持续Bernoulli需求1800秒、统一3000秒物理上限，共6例。此批公共参考供后续另行锁定候选同输入配对，不运行91–93最终种子。

候选标签S只用于固定共同规则源；运行mode为noa，不是transform。规则直接取600秒基线冻结的S源，SHA256 `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`，461行；原runner其余九源仍固定提交 `177f7a32088fb69efcc94d9acb72863e7e00e787`。所有原物理、道路、0.1秒步长、1秒变道、巡航28.8、最高33.3m/s、入口、安全及NOA容量保持；不叠V/F，不改生产。

jobs2，单例墙钟2400秒（原更高流量2250档1800秒需求曾约542/1001秒；本阶段不运行该高档），外层7200秒。墙钟限制不当作道路排空时间，每case完整结束才评价；执行故障、未完成和碰撞保留。优先交通计算，原runner逐例紧凑验封保证恢复；集中大包压缩后置。

```powershell
python -B scripts/run_logged.py --label midflow-long1800-NOA81-6 --timeout 7200 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate S=tmp/staggered_bottleneck/20261103_midflow_baseline71_24/sources/S/noa/native_rules.py --stage midflow_long1800_NOA81 --flows 1500 1750 2000 --seeds 81 82 --scenarios lane_drop --modes noa --duration 1800 --max-time 3000 --jobs 2 --worker-timeout 2400 --output tmp/staggered_bottleneck/20261103_midflow_long1800_NOA81_6
```

新raw目录独占，逐例run_logged及原件/compact/ledger/离线封存复用旧工具，不重用旧尝试。全部positions/events先保留供机制agent及全程窗口核验；后续非展示成功case只在机制提取、离线归档可恢复且原件SHA一致后精确清理，失败不删。展示scope与清理清单在实际删除前另记，不据性能挑删除范围。

原固定[100,600)指标原样保留，不能冒称1800秒全程。另直接复用旧`report_long_window.py`从完整封存region_steps与所有gate bracket重算[100,1800)共同需求窗，仍800≤x<1000米、三道长度0.6车道公里、v<5m/s，区域按[start,end)积分，首次gate越线沿原闭端定义。TT/系统时间/入口等待/燃油/分段/旗标仍是原全需求或全轨迹指标，不用窗口裁切替换。

```powershell
python -B scripts/run_logged.py --label midflow-long1800-NOA81-window --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/report_long_window.py --batch tmp/staggered_bottleneck/20261103_midflow_long1800_NOA81_6 --baseline S --target S --start 100 --end 1800 --output docs/experiments/2026-11-03-midflow-staggered/long1800_NOA81_6/window_100_1800
```

此NOA-only批没有transform配对，先产逐例窗口与账本来源核验。最终候选另批完成并锁定后，合并两批同flow/seed/scenario配对，差值候选减NOA、种子等权；不补缺项、不改原评价。控制保持本车/有限局部观测/自身记忆，禁止隐含通信、全局调度、真实ID优先权。Git由root统一执行。
