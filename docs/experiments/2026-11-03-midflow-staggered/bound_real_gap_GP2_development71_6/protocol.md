# GP2的600秒development：71/72，六例缩道增量

2026-11-03 20:04（Asia/Shanghai）结果前登记，root授权继续。GP2源保持523行SHA256 `37306e86a8e0e1045763bf54ebb3adca60ebc489dde6925a61553240ad0195cc`，路径`tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_v2/native_rules.py`，本批不改源，不叠F/V/C5或尚未ready的密度缓冲候选。

每道1500/1750/2000辆/h、已见development种子71/72、lane_drop、transform、600秒连续Bernoulli请求、1200秒物理上限，共6例。直接复用`20261103_midflow_baseline71_24`中S同输入缩道transform六例，S规则锁定SHA `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`，不重跑S或NOA。GP2直路scope合同可证明dropNone回S，但本批不模拟直路，只报告缩道增量配对，不把未跑直路当实测DID。

原runner九个非规则源固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`，原物理/道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/SUMO安全/NOA容量保持，生产不动。jobs2、单例墙钟1800秒、外层7200秒；已有S1800最后一例原jobs1继续，总3模拟。全6矩阵完成后才评价，碰撞/未完成/执行失败/无改善/燃油代价全留。最终91–95仍禁启动。

```powershell
python -B scripts/run_logged.py --label midflow-GP2-development71-6 --timeout 7200 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate GP2=tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_v2/native_rules.py --stage midflow_GP2_development71 --flows 1500 1750 2000 --seeds 71 72 --scenarios lane_drop --modes transform --duration 600 --max-time 1200 --jobs 2 --worker-timeout 1800 --output tmp/staggered_bottleneck/20261103_midflow_GP2_development71_6
```

全部raw先完整保留待全量/post5/兼容带及触发审计，至少seed71三档三例完整positions/events长期保留；其他成功case仅在原件/完整紧凑包/隔离离线复核、机制提取并明确放行后精确清理，失败不删。旧批及原manifest/seal只读，Git由root统一处理。

```powershell
python -B scripts/run_logged.py --label midflow-GP2-development71-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_baseline71_24 tmp/staggered_bottleneck/20261103_midflow_GP2_development71_6 --reference S --output docs/experiments/2026-11-03-midflow-staggered/bound_real_gap_GP2_development71_6/analysis
```

正式只取`GP2-minus-S_transform`六个lane_drop配对，原需求/参数/非规则源及完整[100,600)门禁照用。系统时间为主，并列行程、入口等待、燃油、瓶颈段、区域/低速/越线及0/1，种子等权，不补缺项、不称容量。实际CTH入窗/post5机制另列；新post5严格S完整raw参考目前仅seed71缩道三例，不冒称两种子全raw机制配对。控制始终只用本车/有限局部观测/自身记忆。
