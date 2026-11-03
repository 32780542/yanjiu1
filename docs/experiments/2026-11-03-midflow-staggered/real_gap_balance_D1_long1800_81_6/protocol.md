# D1持续1800秒确认：81/82，六例

2026-11-03 21:30（Asia/Shanghai）结果前登记，root授权jobs2，另并行DR/DP600 jobs4。D1仍423行，SHA2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a，源tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py始终不改。1500/1750/2000每道流量、81/82、lane_drop、transform、1800秒连续Bernoulli请求、3000秒物理上限，共6例。

主要比较D1减同81/82的S-transform六例，次比较公共NoA六例，参考均已冻结，不重跑。九个非规则源继续原runner固定BASE177f7a32088fb69efcc94d9acb72863e7e00e787，原道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/物理安全/NoA容量保持，生产仍S，不叠GP/B/V/F。jobs2、单例墙钟2400秒、外层7200秒。全6完成后评价，失败/碰撞/未完成/小效应/负效应照留，最终91–95未授权前禁跑。

```powershell
python -B scripts/run_logged.py --label midflow-long1800-D1-81-6 --timeout 7200 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate D=tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py --stage midflow_long1800_D1_81 --flows 1500 1750 2000 --seeds 81 82 --scenarios lane_drop --modes transform --duration 1800 --max-time 3000 --jobs 2 --worker-timeout 2400 --output tmp/staggered_bottleneck/20261103_midflow_long1800_D1_81_6
```

所有raw留到审计/本轮收口，至少81三档三例长期全raw保留，失败不删。新raw独占，旧批/manifest/seal/工具不改，Git由root负责。只drop，不报告未跑long直路DID。

```powershell
python -B scripts/run_logged.py --label midflow-long1800-D1-81-pairs --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_long1800_NOA81_6 tmp/staggered_bottleneck/20261103_midflow_long1800_S81_6 tmp/staggered_bottleneck/20261103_midflow_long1800_D1_81_6 --reference S --output docs/experiments/2026-11-03-midflow-staggered/real_gap_balance_D1_long1800_81_6/analysis_original_window
python -B scripts/run_logged.py --label midflow-long1800-D1-81-window --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/report_long_window.py --batch tmp/staggered_bottleneck/20261103_midflow_long1800_NOA81_6 tmp/staggered_bottleneck/20261103_midflow_long1800_S81_6 tmp/staggered_bottleneck/20261103_midflow_long1800_D1_81_6 --baseline S --target S D --start 100 --end 1800 --output docs/experiments/2026-11-03-midflow-staggered/real_gap_balance_D1_long1800_81_6/window_100_1800
```

第一条核D1减S六对源/请求/参数门禁，原[100,600)区域指标保留。第二条从完整region_steps/gate brackets复算[100,1800)，S/D1分别对同NoA作六对；扩展窗D1减S从两者正式target值直接相减，逐项核共同参考一致及同mode资格，复用原方法不改评价阈值。完整系统/行程/入口/燃油与窗口区域/低速/越线明确区分，种子等权，不补值、不称容量，控制只用本车/有限局部观测/自身记忆。
