# V2对冻结S短筛：73/74，6个新增case

2026-11-03 18:49（Asia/Shanghai）结果产生前登记，root明确授权。候选W为V2，仅移除V1接收者自身过640米的门槛；终止车仍需在640–1000米且正前方50米内，规则源和测试由root锁定。源路径`tmp/staggered_bottleneck/candidates/midflow_projected_predecessor_v2/native_rules.py`，470行，SHA256 `7958774c263a202cc075feb11b3c538275c8cfe636fff483c9b5f09d524d381b`。不叠加F或其他候选，不改生产。

每道1500/1750/2000辆/h、种子73/74、lane_drop、transform、180秒连续需求、500秒物理上限，W共6例，jobs1、单例墙钟1200秒、外层3600秒。其余九源沿原runner固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`，原物理、安全、入口、NOA容量不变。控制仍只用本车、有限局部观测和自身记忆。

比较参考直接复用`20261103_midflow_V1_screen73_12`中相同流量/种子/道路/mode的6个锁定S case（SHA `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`），不重复模拟S。W减S为本批正式差值，V1结果作为独立迭代记录保留。每case完整结束才评价，失败、未完成、碰撞及无改善均保留；禁止91–93最终种子。

```powershell
python -B scripts/run_logged.py --label midflow-V2-screen73-6 --timeout 3600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate W=tmp/staggered_bottleneck/candidates/midflow_projected_predecessor_v2/native_rules.py --stage midflow_V2_screen73 --flows 1500 1750 2000 --seeds 73 74 --scenarios lane_drop --modes transform --duration 180 --max-time 500 --jobs 1 --worker-timeout 1200 --output tmp/staggered_bottleneck/20261103_midflow_V2_screen73_6
```

所有raw先完整保留供机制agent提取。至少保留seed73三例全positions/events，其他成功case仅在机制提取、完整紧凑封包及原件/离线验核后调用旧prune_raw精确清理；失败不删。新raw目录独占，旧批不改，Git由root统一处理。

```powershell
python -B scripts/run_logged.py --label midflow-V2-screen73-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_V1_screen73_12 tmp/staggered_bottleneck/20261103_midflow_V2_screen73_6 --reference S --output docs/experiments/2026-11-03-midflow-staggered/projected_predecessor_v2_screen73_6/analysis
```

正式仅取`W-minus-S_transform`六对，原工具需通过共同需求、参数及非规则源的配对门禁。原[100,600)完整窗口不足照留空值；机制诊断[30,180)共同需求窗单独记录，不改评价器。两种子等权、主指标系统时间，行程/入口等待/燃油/瓶颈段/变道/0-1几何负结果照录。
