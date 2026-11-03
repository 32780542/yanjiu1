# 独立未来资源F2对冻结S短筛：73/74，6个新增case

2026-11-03 18:59（Asia/Shanghai）在本批结果前登记，root授权并行1job。候选F源`tmp/staggered_bottleneck/candidates/midflow_future_resources_v2/native_rules.py`，SHA256 `d07c82501e3e86ce06529779b9c0bacd9469fd9654cc43c6dcd1c81bb21f8be4`。从S独立修改_fill未来资源图π0=0、π1=π2=1，未来load/phase/full/vacancy一致，实际执行仍现有gap闭环。定义为未来资源指导选道，不是指定未来slot跟踪；不叠V/W、不改生产。方法/局部合同由root与方法agent负责，见candidates/future_resources及future_resources_v2。

每道1500/1750/2000辆/h、种子73/74、lane_drop、transform、180秒连续Bernoulli请求、统一500秒物理上限，共6例。原runner九个非规则源固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`，原道路、0.1秒步长、1秒变道、巡航28.8/最高33.3m/s、入口、安全和NOA容量保持。jobs1、单例墙钟1200秒、外层3600秒，与公共NOA1800秒批jobs2并行；不跑91–93最终种子。

正式比较F-transform减S-transform，直接复用`20261103_midflow_V1_screen73_12`同flow/seed/scenario/mode六例冻结S参考（规则SHA `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`），不重复模拟S。所有case完整结束才评价；碰撞、未完成、执行失败、无改善和燃油代价照留，不把墙钟当交通表现。

```powershell
python -B scripts/run_logged.py --label midflow-F2-screen73-6 --timeout 3600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate F=tmp/staggered_bottleneck/candidates/midflow_future_resources_v2/native_rules.py --stage midflow_F2_screen73 --flows 1500 1750 2000 --seeds 73 74 --scenarios lane_drop --modes transform --duration 180 --max-time 500 --jobs 1 --worker-timeout 1200 --output tmp/staggered_bottleneck/20261103_midflow_F2_screen73_6
```

全部raw先保留待机制agent提取，至少73三例positions/events完整保留。其他成功case只有原件/完整紧凑封包/离线验核、机制提取完成后才调用旧prune_raw精确清理；失败不删。独占新目录，旧批只读，Git由root负责。

```powershell
python -B scripts/run_logged.py --label midflow-F2-screen73-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_V1_screen73_12 tmp/staggered_bottleneck/20261103_midflow_F2_screen73_6 --reference S --output docs/experiments/2026-11-03-midflow-staggered/future_resources_F2_screen73_6/analysis
```

正式只取`F-minus-S_transform`六对，公共需求、参数、非规则源与完整性门禁沿用原工具。主指标完整请求系统时间，另列路内行程、真实入口等待、燃油、瓶颈段、变道和原0/1。原[100,600)formal窗口不足保持空值；单独机制[30,180)窗口不改原评价。种子等权，不补缺项，不把参与人数称单支编队大小。
