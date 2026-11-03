# 独立容量匹配预形成B短筛：73/74，6例

2026-11-03 20:19（Asia/Shanghai）结果前登记，root授权jobs2，接已完整结束G0的槽位，当前与GP2 development600 jobs2合计4模拟。B从S独立构建，468行，源`tmp/staggered_bottleneck/candidates/midflow_capacity_spacing/native_rules.py`，SHA256 `7d749ba8919efbf06efc0abd43846dee4c13b886e81019ae89c0f0116a1553d2`。不叠GP/V/F/C5，冻结源后方法/场景补充不改本批源。

B在x<640米组织同道45米、相邻22.5米，取原30/15的3/2；之后恢复原30/15。设计依据是巡航密度3/45=2/30匹配，真实map/percar phase一致。实际gap、CF代价、物理安全、NOA原样；不改巡航/最高速度/物理/入口，不增加额外gate等待。均衡与真实90米witness bridge、scope合同由root负责，名义密度匹配不等于实测缩道提效，必须保留实际排空/局部制动/燃油结果。

每道1500/1750/2000辆/h、73/74、lane_drop、transform、180秒连续Bernoulli请求、500秒物理上限，共6例。jobs2、单例墙钟1200秒、外层3600秒。九个非规则源仍由原runner固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`，原道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/SUMO安全/NOA容量保持。最终91–95尚未锁源，不启动。

参考直接复用`20261103_midflow_V1_screen73_12`的同输入S六例，S锁定SHA `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`，不重跑S。全6结束后才评价，失败/碰撞/未完成/无改善/燃油代价全部保留。

```powershell
python -B scripts/run_logged.py --label midflow-B-screen73-6 --timeout 3600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate B=tmp/staggered_bottleneck/candidates/midflow_capacity_spacing/native_rules.py --stage midflow_B_screen73 --flows 1500 1750 2000 --seeds 73 74 --scenarios lane_drop --modes transform --duration 180 --max-time 500 --jobs 2 --worker-timeout 1200 --output tmp/staggered_bottleneck/20261103_midflow_B_screen73_6
```

所有raw先完整保留供预形成几何、进入640米后恢复、实际合流及post5审计，至少seed73三例完整positions/events长期保留，其他成功case仅在原件/完整紧凑包/隔离离线复核、机制明确放行后才精确清理，失败不删。新目录独占，旧批/manifest/seal只读，Git由root统一处理。

```powershell
python -B scripts/run_logged.py --label midflow-B-screen73-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_V1_screen73_12 tmp/staggered_bottleneck/20261103_midflow_B_screen73_6 --reference S --output docs/experiments/2026-11-03-midflow-staggered/capacity_spacing_B_screen73_6/analysis
```

正式只取`B-minus-S_transform`六对，原需求/参数/非规则源门禁照用。完整请求系统时间为主，并列行程/入口等待/燃油/瓶颈段/变道/0-1，种子等权。原[100,600)formal窗不足不补值，共同[30,180)机制窗单列，不把窗口越线叫容量，不把flag人数叫单支编队规模。控制只用本车/有限局部观测/自身记忆，密度设计不引入全局流量真值或通信。
