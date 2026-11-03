# 锁定S的1800秒持续需求参考：81/82，6例

2026-11-03 19:17（Asia/Shanghai）在本批结果前登记，root授权立即续跑。S原锁定规则SHA256 `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`，直接取baseline71冻结源，不改生产。1500/1750/2000每道流量、81/82种子、lane_drop、transform，1800秒持续Bernoulli请求、3000秒物理上限，共6例。

正式参考复用刚完成公共NOA六例`20261103_midflow_long1800_NOA81_6`，同flow/seed/scenario请求配对，不重复NOA。两批均用原runner固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`九个非规则源，原道路、0.1秒步长、1秒变道、巡航28.8/最高33.3m/s、入口、安全与NOA容量保持。

jobs1、单例墙钟2400秒、外层7200秒；同时另批F/C5 development600 jobs2，总3模拟优先。全部case完成才评价；碰撞、未完成、执行失败和无改善保留，墙钟不当作驾驶性能。最终91–95种子不运行。

```powershell
python -B scripts/run_logged.py --label midflow-long1800-S81-6 --timeout 7200 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate S=tmp/staggered_bottleneck/20261103_midflow_baseline71_24/sources/S/noa/native_rules.py --stage midflow_long1800_S81 --flows 1500 1750 2000 --seeds 81 82 --scenarios lane_drop --modes transform --duration 1800 --max-time 3000 --jobs 1 --worker-timeout 2400 --output tmp/staggered_bottleneck/20261103_midflow_long1800_S81_6
```

所有raw先完整保留供全程/变道后制动机制审计，至少seed81三流量三例完整positions/events长期保留。非展示成功case须机制提取完成、原件/完整紧凑包/隔离离线验核后才精确清理，失败不删。新目录独占，旧批及原manifest/seal不改，Git由root负责。

原[100,600)账本/指标不覆盖；完整共同需求窗另用原方法从封存完整region_steps/gate brackets重算[100,1800)。区域仍800–1000米、三道长度0.6车道公里、v<5m/s，区间按[start,end)，首次gate越线沿原闭端定义。系统/行程/入口/燃油/分段/旗标沿原全需求或全轨迹值，不能用600窗充当1800全程。

```powershell
python -B scripts/run_logged.py --label midflow-long1800-S81-window --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/report_long_window.py --batch tmp/staggered_bottleneck/20261103_midflow_long1800_NOA81_6 tmp/staggered_bottleneck/20261103_midflow_long1800_S81_6 --baseline S --target S --start 100 --end 1800 --output docs/experiments/2026-11-03-midflow-staggered/long1800_S81_6/window_100_1800
```

差值S减NOA、种子等权，完整请求系统时间为主，并列行程、入口等待、燃油、瓶颈段、全程区域/越线/低速及0/1。不补缺项、不把窗口越线称容量，控制保持本车/有限局部观测/自身记忆，不叠V/F/C5/GP。
