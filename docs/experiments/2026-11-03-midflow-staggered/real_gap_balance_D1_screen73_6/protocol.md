# 真实gap负荷均衡D1：73/74，6例短筛

2026-11-03 21:04（Asia/Shanghai）结果前登记，root授权jobs2。candidate标签D，源`tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py`，423行，SHA256 `2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a`。D0已登记但未启动，原因/零执行记录见../real_gap_balance_D_screen73_6/not_run.json；不能把D0冒认D1。

D1从S独立替换_fill/_decide，以actual gap和未来资源负荷势能下降选择真实相邻道，移除grid/full层保护，observed vy/y投影目的道只计一次，可见±90内ending车过640时存续道提前两资源均衡；lane2必要merge仍640。相对D0唯一修复是scoring排除ego，与实际_join rows契约一致，没有改gain/threshold。CTH/phase30/15、response_cost原块、物理安全与NoA保持，不叠GP/B/V/F。冻结后额外状态归因不改本批源。

每道1500/1750/2000辆/h、73/74、lane_drop、transform、180秒连续Bernoulli请求、500秒物理上限，共6例，jobs2、单例墙钟1200秒、外层3600秒。原runner九个非规则源固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`，原物理/道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/SUMO安全/NOA容量不变，生产仍S。

共同S六例复用`20261103_midflow_V1_screen73_12`的73/74同输入transform，S锁定SHA8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f，不重跑。全6结束后才评价，碰撞/失败/未完成/无改善/燃油代价照留。先向root回完整短筛结果，经root确认后才另启动600秒71/72双道路12例；最终91–95仍禁启动。

```powershell
python -B scripts/run_logged.py --label midflow-D1-screen73-6 --timeout 3600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate D=tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py --stage midflow_D1_screen73 --flows 1500 1750 2000 --seeds 73 74 --scenarios lane_drop --modes transform --duration 180 --max-time 500 --jobs 2 --worker-timeout 1200 --output tmp/staggered_bottleneck/20261103_midflow_D1_screen73_6
```

全部raw完整保留待实际gap评分/同帧执行/局部触发/post5审计，至少seed73三例长期完整保留；到本轮收口前不提前清理，失败不删。旧批/manifest/seal/旧工具不改，Git由root负责。控制只读本车/有限局部观测/自身记忆，不用全局槽位/车型真值/隐含通信。

```powershell
python -B scripts/run_logged.py --label midflow-D1-screen73-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_V1_screen73_12 tmp/staggered_bottleneck/20261103_midflow_D1_screen73_6 --reference S --output docs/experiments/2026-11-03-midflow-staggered/real_gap_balance_D1_screen73_6/analysis
```

正式D-minus-S_transform六对，原源/需求/参数门禁照用。完整请求系统时间为主，并列行程/入口/燃油/瓶颈段/变道/0-1，种子等权；180秒原[100,600)formal窗不足留空值，[30,180)机制及post5另列，不补值、不称道路容量。
