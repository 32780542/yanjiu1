# 独立局部gap轨迹C5对冻结S短筛：73/74，6个新增case

2026-11-03 19:03（Asia/Shanghai）结果前登记，按root授权在F2六例结束后启动jobs1，避免第四个模拟争抢。C5从S独立修改organized gap接近轨迹，不叠V/W/F。源`tmp/staggered_bottleneck/candidates/midflow_local_gap_trajectory/native_rules.py`，469行，SHA256 `35aeef86dd7d720b8897451853f4a5c89d7786f18765ba283eb05396e9f55def`。

设计使用本地移动端点、T=5秒最小∫a²初始控制`a=6e/T²+4dv/T`，仅在organized gap追踪生效。NOA、基础CTH、安全裁剪、变道门禁及实际gap执行闭环保持S原样。定义、推导和公开红绿合同由root负责；较小加速度不作为交通成功，必须看完整结束后的系统时间与是否把制动推迟至回CTH之后。

每道1500/1750/2000辆/h、73/74种子、lane_drop、transform、180秒持续Bernoulli请求、500秒物理上限，共6例，jobs1、单例墙钟1200秒、外层3600秒。其余九源沿原runner固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`。原物理/道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/安全/NOA容量不变，生产不动，不跑91–93最终种子。

正式比较C5-transform减S-transform，直接复用`20261103_midflow_V1_screen73_12`中同flow/seed/scenario/mode冻结S六例，S规则SHA `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`，不重跑S。case完整结束才评价，碰撞、未完成、执行失败、无改善和燃油代价全部保留。

```powershell
python -B scripts/run_logged.py --label midflow-C5-screen73-6 --timeout 3600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate C5=tmp/staggered_bottleneck/candidates/midflow_local_gap_trajectory/native_rules.py --stage midflow_C5_screen73 --flows 1500 1750 2000 --seeds 73 74 --scenarios lane_drop --modes transform --duration 180 --max-time 500 --jobs 1 --worker-timeout 1200 --output tmp/staggered_bottleneck/20261103_midflow_C5_screen73_6
```

所有raw先完整保留供机制agent提取，至少seed73三例全positions/events长期保留；其他成功case须原件/完整紧凑封包/隔离离线复核、机制提取完后才用旧prune_raw精确清理，失败不删。新raw目录独占，旧尝试只读，Git由root统一处理。

```powershell
python -B scripts/run_logged.py --label midflow-C5-screen73-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_V1_screen73_12 tmp/staggered_bottleneck/20261103_midflow_C5_screen73_6 --reference S --output docs/experiments/2026-11-03-midflow-staggered/local_gap_trajectory_C5_screen73_6/analysis
```

只取`C5-minus-S_transform`六对，原需求/参数/非规则源门禁照用。主指标完整请求系统时间，并列行程、真实入口等待、燃油、瓶颈段、变道、原0/1，种子等权。原[100,600)formal窗不足不补值；单独机制[30,180)窗和回CTH后制动审计另记，不替换原评价或只报a较小。
