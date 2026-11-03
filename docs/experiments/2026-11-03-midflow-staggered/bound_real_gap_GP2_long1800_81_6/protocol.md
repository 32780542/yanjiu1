# GP2持续1800秒：81/82，六例

2026-11-03 20:36（Asia/Shanghai）结果前登记，root授权在BC恢复/归档后继续。源保持523行GP2，SHA256 `37306e86a8e0e1045763bf54ebb3adca60ebc489dde6925a61553240ad0195cc`，路径`tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_v2/native_rules.py`，不叠其他候选，不改生产S。

1500/1750/2000每道流量、81/82、lane_drop、transform、1800秒连续Bernoulli请求、3000秒物理上限，共6例，jobs2、单例墙钟2400秒、外层7200秒。原九个非规则源仍固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`，原道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/SUMO安全/NOA容量不变。全6结束后才评价，失败/碰撞/未完成/无改善/燃油代价保留，最终源未锁，91–95禁启动。

主要比较GP2-transform减已有`20261103_midflow_long1800_S81_6`同输入S-transform六例，检验600秒的温和增量是否持续；次比较GP2与公共`20261103_midflow_long1800_NOA81_6`六例。S与NOA都不重跑。只drop，不把未跑1800直路称实测DID。

```powershell
python -B scripts/run_logged.py --label midflow-long1800-GP2-81-6 --timeout 7200 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate GP2=tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_v2/native_rules.py --stage midflow_long1800_GP2_81 --flows 1500 1750 2000 --seeds 81 82 --scenarios lane_drop --modes transform --duration 1800 --max-time 3000 --jobs 2 --worker-timeout 2400 --output tmp/staggered_bottleneck/20261103_midflow_long1800_GP2_81_6
```

全部raw先完整保留待全程/入窗/触发/post5匹配审计，至少seed81三例完整positions/events长期保留，其余到本轮收口前不提前清理；任何失败raw保持。旧批/manifest/seal只读，Git由root负责。

```powershell
python -B scripts/run_logged.py --label midflow-long1800-GP2-81-pairs --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_long1800_NOA81_6 tmp/staggered_bottleneck/20261103_midflow_long1800_S81_6 tmp/staggered_bottleneck/20261103_midflow_long1800_GP2_81_6 --reference S --output docs/experiments/2026-11-03-midflow-staggered/bound_real_gap_GP2_long1800_81_6/analysis_original_window
python -B scripts/run_logged.py --label midflow-long1800-GP2-81-window --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/report_long_window.py --batch tmp/staggered_bottleneck/20261103_midflow_long1800_NOA81_6 tmp/staggered_bottleneck/20261103_midflow_long1800_S81_6 tmp/staggered_bottleneck/20261103_midflow_long1800_GP2_81_6 --baseline S --target S GP2 --start 100 --end 1800 --output docs/experiments/2026-11-03-midflow-staggered/bound_real_gap_GP2_long1800_81_6/window_100_1800
```

第一条给正式GP2减S六对及源/需求/参数门禁，原[100,600)区域指标保留不覆盖。第二条复用原完整region_steps/gate brackets重算[100,1800)，同时生成S/GP2各自相对同一NOA的六对。扩展窗口的GP2减S指标从这两组共同NOA参考的target值直接相减，逐流量/种子核对同参考及第一条六对资格，不修改原报告器或评价阈值。

主指标仍完整请求系统时间，并列行程/入口/燃油/640–1100段及全程区域/低速/越线/0-1，种子等权；区间、低速阈值与旧方法相同，不补值、不称容量。完整需求指标与时间窗指标明确区分。控制只读本车/有限局部观测/自身记忆。
