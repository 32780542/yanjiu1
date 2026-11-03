# 独立真实gap负荷均衡D：73/74，6例短筛

2026-11-03 20:59（Asia/Shanghai）结果前登记，root授权立即jobs2。D源423行，`tmp/staggered_bottleneck/candidates/midflow_real_gap_balance/native_rules.py`，SHA256 `afb3ecbe5a432bd2c93e16a21ac88690171266fd37e0c420bc74ea7e6146047e`。从S只替换_fill/_decide，去grid/full层保护，以actual gap及未来资源负荷势能下降选真实相邻车道；observed vy/y投影移动车辆目的道一次。可见±90米内ending车已过640时存续道按两资源均衡，lane2自身必要merge仍640。CTH/phase30/15、安全/NoA不变，评分与_join_speed同帧闭合，response_cost块AST同S，不叠GP/B/V/F。

每道1500/1750/2000辆/h、73/74、lane_drop、transform、180秒连续Bernoulli请求、500秒物理上限，共6例，jobs2、单例墙钟1200秒、外层3600秒。原runner九个非规则源固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`；原道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/物理/NOA容量保持，生产S不改。只用本车/有限局部观测/自身记忆，不用真实车型/全局槽位/隐含通信。

共同S73/74六例直接复用`20261103_midflow_V1_screen73_12`，锁源8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f，不重跑。全6结束才评价，碰撞/失败/未完成/无改善/燃油代价保留。root看短筛结果确认后才能启动D的600秒双道路12例；此授权不自动延伸到该批。最终91–95禁启动。

```powershell
python -B scripts/run_logged.py --label midflow-D-screen73-6 --timeout 3600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate D=tmp/staggered_bottleneck/candidates/midflow_real_gap_balance/native_rules.py --stage midflow_D_screen73 --flows 1500 1750 2000 --seeds 73 74 --scenarios lane_drop --modes transform --duration 180 --max-time 500 --jobs 2 --worker-timeout 1200 --output tmp/staggered_bottleneck/20261103_midflow_D_screen73_6
```

全部raw先完整保留到审计/本轮收口，至少73三例长期完整保留；失败不删。旧批/manifest/seal/旧工具不改，Git由root统一处理。

```powershell
python -B scripts/run_logged.py --label midflow-D-screen73-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_V1_screen73_12 tmp/staggered_bottleneck/20261103_midflow_D_screen73_6 --reference S --output docs/experiments/2026-11-03-midflow-staggered/real_gap_balance_D_screen73_6/analysis
```

正式仅D-minus-S_transform六对，原源/需求/参数门禁照用。完整请求系统时间为主，并列行程/入口/燃油/瓶颈段/变道/0-1，种子等权；原[100,600)formal窗不足留空值，[30,180)机制及post5另列，不补值、不称道路容量。
