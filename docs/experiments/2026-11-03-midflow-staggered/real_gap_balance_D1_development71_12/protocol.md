# D1持续600秒双道路development：71/72，12例

2026-11-03 21:14（Asia/Shanghai）结果前登记，root已查看D1短筛完整六例并明确授权立即jobs4。D1仍423行，源`tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py`，SHA256 `2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a`，不改源，不叠GP/B/V/F。

candidate D × 每道1500/1750/2000辆/h × 已见71/72 × straight3/lane_drop × transform，共12例，600秒连续Bernoulli请求、1200秒物理上限。共同参考直接复用baseline71_24中S的同输入transform12例，S SHA8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f，不重复S/NOA。jobs4、单例墙钟1800秒、外层7200秒。可并行DR/DP短筛jobs2，总6模拟已由root授权。

九个非规则源固定旧runner BASE177f7a32088fb69efcc94d9acb72863e7e00e787，原道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/物理安全/NoA容量保持，生产S不改。完整12矩阵结束后才判断系统时间与DID，失败/碰撞/未完成/无改善/燃油代价全部保留，最终91–95尚未锁候选，禁启动。

```powershell
python -B scripts/run_logged.py --label midflow-D1-development71-12 --timeout 7200 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate D=tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py --stage midflow_D1_development71 --flows 1500 1750 2000 --seeds 71 72 --scenarios straight3 lane_drop --modes transform --duration 600 --max-time 1200 --jobs 4 --worker-timeout 1800 --output tmp/staggered_bottleneck/20261103_midflow_D1_development71_12
```

全部raw完整保留供全量/post5/实际gap及局部负荷机制审计，至少seed71/lane_drop三档三例长期全raw保留；收口前不提前清理，失败不删。新raw独占，旧批/manifest/seal/旧工具只读，Git仅root执行。

```powershell
python -B scripts/run_logged.py --label midflow-D1-development71-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_baseline71_24 tmp/staggered_bottleneck/20261103_midflow_D1_development71_12 --reference S --output docs/experiments/2026-11-03-midflow-staggered/real_gap_balance_D1_development71_12/analysis
```

正式D减S同mode12对，原源/需求/参数/完整[100,600)门禁照用。主指标系统时间，DID为同种子缩道差值减直路差值，负值代表额外缩道节省；并列行程/入口/燃油/瓶颈段/区域/低速/越线/0-1，种子等权，不补值、不称容量。严格新增post5共同S完整raw参考目前仅71缩道三例，不把其余未保留raw冒称全量机制面板。控制只用本车/有限局部观测/自身记忆，不用全局槽位/真车型/通信。
