# 独立统一真实gap GP短筛：73/74，6例

2026-11-03 19:29（Asia/Shanghai）本批结果前登记，root明确授权加独立jobs1，使当前总模拟从3升至4（本机32 logical CPUs，D盘约14GB）。GP从S独立构建，不叠V/W/F/C5。冻结源`tmp/staggered_bottleneck/candidates/midflow_bound_real_gap/native_rules.py`，514行，SHA256 `3e2a722f997713e6ad504bce22d741c39d58b1ad6808765a5b9b8d62a68a1007`；后续同架构检查不得修改本批已冻结源。

GP在transform准备区目标lane1中，用局部实际pair与地图剩余时间构造名义CTH窗及min-energy接近，持有同pair，以原实际8米clear执行；NOA、formation、直路和target0保持S原样。资源不足moving时原S继续。名义终点CTH可行不自动等于提前横移后无压缩，必须保留实际横移/接收后车/post5制动等机制负结果。控制仍只读本车、有限局部观测与自身记忆，不用通信、全局调度、车型真值或真实ID优先权。

每道1500/1750/2000辆/h、73/74种子、lane_drop、transform、180秒持续Bernoulli请求、500秒物理上限，共6例。旧runner九个非规则源仍固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`，原物理/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/安全/NOA容量不变，生产不动。jobs1、单例墙钟1200秒、外层3600秒；91–95最终种子不启动。

S参考直接复用`20261103_midflow_V1_screen73_12`相同flow/seed/scenario/mode的S六例，SHA `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`，不重复S。完整6例结束后才评价，失败/碰撞/未完成/无改善照录，不把较小a或名义可行当作成功。

```powershell
python -B scripts/run_logged.py --label midflow-GP-screen73-6 --timeout 3600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate GP=tmp/staggered_bottleneck/candidates/midflow_bound_real_gap/native_rules.py --stage midflow_GP_screen73 --flows 1500 1750 2000 --seeds 73 74 --scenarios lane_drop --modes transform --duration 180 --max-time 500 --jobs 1 --worker-timeout 1200 --output tmp/staggered_bottleneck/20261103_midflow_GP_screen73_6
```

所有raw先完整保留待全量/post5审计，至少seed73三例全positions/events长期保留；其余成功case须原件/完整紧凑包/隔离离线复核、机制提取完后才精确清理，失败不删。新raw独占，旧批及原manifest/seal只读，Git由root统一处理。

```powershell
python -B scripts/run_logged.py --label midflow-GP-screen73-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_V1_screen73_12 tmp/staggered_bottleneck/20261103_midflow_GP_screen73_6 --reference S --output docs/experiments/2026-11-03-midflow-staggered/bound_real_gap_GP_screen73_6/analysis
```

正式仅取`GP-minus-S_transform`六对，原需求/参数/非规则源门禁照用。主指标完整请求系统时间，并列行程、入口等待、燃油、瓶颈段、变道和0/1，种子等权。原[100,600)formal区域窗不足保持空值；共同[30,180)机制窗和回CTH/post5诊断单列，不替换原评价。
