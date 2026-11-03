# GP2统一真实gap规划与入窗：73/74，6例短筛

2026-11-03 19:46（Asia/Shanghai）结果前登记，root授权接续原GP空出的jobs1，总模拟仍为S1800 jobs1 + development600 jobs2 + 本批jobs1。源`tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_v2/native_rules.py`，523行，SHA256 `37306e86a8e0e1045763bf54ebb3adca60ebc489dde6925a61553240ad0195cc`。从S独立完整规划，不叠F/V/C5；原GP尝试与源不改。

GP2对held gap优先，在T=5秒及地图剩余时间之间选最短名义可行T，再按J；除原实际8米clear外，未开始横移者需在当前CTH±已有2米兼容带。moving/pending继续，无资源时回退原S。时域更改用于修正固定最大剩余T/roadguard排除前方gap的几何限制，scope/admission与名义cubic合同由root负责。实际横移/接收后车/post5证据仍需审计，名义可行或更小a不等同交通成功。

1500/1750/2000每道流量、73/74、lane_drop、transform、180秒连续Bernoulli请求、500秒物理上限，共6例。jobs1、单例墙钟1200秒、外层3600秒。旧runner九个非规则源固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`，原道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/SUMO安全/NOA容量不变，生产不动，91–95最终种子禁启动。

直接复用`20261103_midflow_V1_screen73_12`中同flow/seed/scenario/mode的S六例，S锁定SHA `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`，不重跑S。全6例完成后才评价，失败/碰撞/未完成/无改善和燃油代价均保留。

```powershell
python -B scripts/run_logged.py --label midflow-GP2-screen73-6 --timeout 3600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate GP2=tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_v2/native_rules.py --stage midflow_GP2_screen73 --flows 1500 1750 2000 --seeds 73 74 --scenarios lane_drop --modes transform --duration 180 --max-time 500 --jobs 1 --worker-timeout 1200 --output tmp/staggered_bottleneck/20261103_midflow_GP2_screen73_6
```

所有raw先完整保留待全量/post5/实际兼容带审计，至少seed73三例完整positions/events长期保留；其余成功case须原件/完整紧凑包/隔离离线复核、机制提取完后才精确清理，失败不删。新raw独占，旧尝试及原manifest/seal只读，Git由root统一处理。

```powershell
python -B scripts/run_logged.py --label midflow-GP2-screen73-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_V1_screen73_12 tmp/staggered_bottleneck/20261103_midflow_GP2_screen73_6 --reference S --output docs/experiments/2026-11-03-midflow-staggered/bound_real_gap_GP2_screen73_6/analysis
```

正式仅取`GP2-minus-S_transform`六对，原需求/参数/非规则源门禁照用。主指标完整请求系统时间，并列行程、入口等待、燃油、瓶颈段、变道及原0/1，种子等权。原[100,600)formal窗口不足保持空值；共同[30,180)机制窗/post5单列，不替换原评价。控制只用本车/有限局部观测/自身记忆，不用通信、全局槽位或真实ID优先权。
