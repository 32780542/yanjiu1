# F2与C5的600秒development：71/72，24个新增case

2026-11-03 19:17（Asia/Shanghai）在本批结果前登记，root授权延长检验。短筛混合效应不能直接视为600秒失败，本批完整矩阵结束后才判断持续效应。只用已见development种子71/72；最终确认已由root在揭盲前扩为91–95五种子，本批不运行或读取它们。

候选各从S独立构建，不互叠：F为未来资源指导选道（不是指定未来slot跟踪），源`midflow_future_resources_v2/native_rules.py`，SHA256 `d07c82501e3e86ce06529779b9c0bacd9469fd9654cc43c6dcd1c81bb21f8be4`；C5为organized gap的T=5秒局部移动端点轨迹，源`midflow_local_gap_trajectory/native_rules.py`，SHA256 `35aeef86dd7d720b8897451853f4a5c89d7786f18765ba283eb05396e9f55def`。两文件均在`tmp/staggered_bottleneck/candidates`。不叠V/W/GP，不改生产。

F/C5 × 每道1500/1750/2000辆/h × 71/72 × straight3/lane_drop × transform，共24例，每候选12例。600秒持续Bernoulli请求、统一1200秒物理上限。共同S参考直接复用`20261103_midflow_baseline71_24`中transform的原12例，S锁定SHA `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`；NOA也不重跑。

旧runner九个非规则源固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`，原物理/道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/安全/NOA容量不变。jobs2，单例墙钟1800秒，外层7200秒；并行S1800 jobs1，总3模拟。集中大包压缩后置。case完整结束才评价，失败/未完成/碰撞/无改善照留。

```powershell
python -B scripts/run_logged.py --label midflow-F2-C5-development71-24 --timeout 7200 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate F=tmp/staggered_bottleneck/candidates/midflow_future_resources_v2/native_rules.py C5=tmp/staggered_bottleneck/candidates/midflow_local_gap_trajectory/native_rules.py --stage midflow_F2_C5_development71 --flows 1500 1750 2000 --seeds 71 72 --scenarios straight3 lane_drop --modes transform --duration 600 --max-time 1200 --jobs 2 --worker-timeout 1800 --output tmp/staggered_bottleneck/20261103_midflow_F2_C5_development71_24
```

所有raw先保留待全量机制/post5审计，至少seed71/lane_drop三流量F/C5共6例全positions/events长期保留；其余成功case只有原件、完整紧凑包、隔离离线验核和机制提取完后才精确清理，失败不删。新raw独占，旧批只读，原manifest/seal不改。

```powershell
python -B scripts/run_logged.py --label midflow-F2-C5-development71-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_baseline71_24 tmp/staggered_bottleneck/20261103_midflow_F2_C5_development71_24 --reference S --output docs/experiments/2026-11-03-midflow-staggered/F2_C5_development71_24/analysis
```

正式比较仅取F/C5减S同mode transform的24对。原工具还会保留S-transform减NOA十二对，不混入候选替换效应。重点逐流量逐种子道路差分：候选减S的lane_drop差值再减straight3差值（DID），特别保留2000档与所有负结果。系统时间为主，并列行程、入口等待、燃油、瓶颈段、原[100,600)区域/低速/越线和0/1，种子等权，原完整性门禁不变。机制另看回CTH后的制动，不以a较小或省油代替交通改善。控制始终只用本车、有限局部观测、自身记忆，Git由root统一执行。
