# NoA60：仅前车作用距离敏感性

独立父源J2fast `03ce8f468bdce13b9db82b7122eeeeb3d688128f3c3c5bb9dd34ab62df28c6a6`。新源 `tmp/staggered_bottleneck/candidates/noa_range60/native_rules.py`，SHA `c5ed30e8c8f722959c97a9db86c857db22e8740a7d7d0c118d1c028ec7550dd2`，450行，仅_front_following增加可选distance=60.0并让原距离过滤引用它。AST只此函数变，反向精确恢复父源，见[patch](native_rules.patch)、[build](build.py)、[身份](source.json)。

**只供NoA模式敏感性，不安装或改写正式基线。** CTH目标、gain=.3、响应=.2、硬安全、物理参数、横向分支、状态0与Memory未改。由于改的是公共helper默认值，formation及cf_speed的默认调用也会看到60m；它们的公式未变，但不要把此源的编队/fill输出解释成纯NoA距离比较。本轮没有创建100m版本，没有跑交通。

[八项合同](../../tests/test_noa_range60.py)在原50m上4项预期失败后，新源8项及4子测试通过，覆盖50–60m真实front绑定、60包含/>60不跟、≤50最近front优先、重标/重排/远车不变、600个已有≤50m front场景的完整NoA Command/Memory/CF精确相同，安全与状态0保留。

## 50m截断的实际源码含义

固定父源的 `_front_following`（line104–113）在0<gap≤50时找真实占道front，目标为 `front.x−5.5−HEADWAY*v_ego`，再用 `_request`（line66–68）。找不到front时直接返回CRUISE，不读取远处前车速度。`_decide`（line313–334）在NoA走此函数并强制formation_state=0，形成分支才用跨道耦合。

在尚未触及0/MAX夹紧、硬安全的情况下，令g为实际front.x−ego.x：

```text
g≤range: v_req = v + .2*(v_front + .3*(g−5.5−HEADWAY*v) − v)
g>range: v_req = CRUISE
```

所以50m确实会产生目标速度切换，并非连续衰减。以ego=28.8m/s为例，front=15时，g49.999的请求27.23994，而g50.001返回28.8；相同巡航front时，前者29.99994、后者28.8。扩大到60可能使慢front更早引起减速，也可能使同速front的空格更早闭合；不能预设它必然更快。

这证明存在**请求速度的不连续**，不能单凭源码断言它已经造成“不真实实际减速”。`native_sumo.py`的物理参数line32–44保留accel5、decel10、tau.2、speedDev0；line668设置SUMO speedMode31，line841–845再次计算原硬安全并setSpeed。真实轨迹还受前车、并入目标及SUMO安全执行影响。NoA60就是为量化截断敏感性而设，不能为维护原结论先假定50m无影响。

## 入口等待的源证据与既有真实数据

`native_sumo.py` line235–252预先把原请求时间/车道/位置/速度写入route；line558–562记录“SUMO native route departures; no Python entry gate”；line668–674只在SUMO实际depart后建立本车Memory/订阅，没有Python入口节流。入口等待由SUMO原生插入可用空间/安全等状态决定，控制可通过道路拥挤间接影响，不能说入口与控制完全无关。

统计定义在line403–405：入口等待=entered−requested；TT=exited−entered；system=exited−requested。40例原结果只读审计见[audit_baseline.py](audit_baseline.py)、[CSV](baseline31_entry_audit.csv)、[原结果/输入SHA及静态切换例](baseline31_entry_audit.json)。这些是已完成的validation31_NOA40，600s需求、seed31–35，每组5例；原TM源的NoA50跟驰/参数与本次父源NoA50相同，未重跑。

| 每道请求流量 | 道路 | 平均入口等待s | 平均在路TT s |
| --- | --- | ---: | ---: |
| 1250 | 3→2 | .042 | 42.122 |
| 1250 | 三道直路 | .042 | 41.763 |
| 2000 | 3→2 | .130 | 44.696 |
| 2000 | 三道直路 | .130 | 41.822 |
| 2250 | 3→2 | .179 | 53.734 |
| 2250 | 三道直路 | .179 | 41.854 |
| 2500 | 3→2 | .324 | 77.403 |
| 2500 | 三道直路 | .269 | 41.918 |

40例全安全排空。2500瓶颈在路TT比1200/28.8=41.667s参考多约35.737s，平均入口等待仅.324s（最大case的均值.610s）。因此现有高流量NOA不能概括为“本来不堵”，总延误也不能主要归于入口等待。组均值不能排除个别车辆更长等待；本审查没有建立50m截断与这些实际延误的因果关系，需父独立同输入NoA60配对。

## 操作与失败留存

- 基线红：`20261103T060733867369Z_NOA60-range-contract-red_3034f4dc`，4失败/4通过/4子测试通过。
- 首次build `20261103T060748876558Z_NOA60-range-source-build_07a51041` 因Windows默认GBK读取中文源失败，未产生候选；随后误启动的绿 `20261103T060750139944Z_NOA60-range-contract-green_ae588d74` 因源不存在collection失败。两者保留，不记为算法失败。
- 显式UTF8构建：`20261103T060823480960Z_NOA60-range-source-build-utf8_79cbc379`，exit0；规则/合同未因编码失败改动。
- 最终绿：`20261103T060834910993Z_NOA60-range-contract-green-utf8_447a5d54`，8项/4子测试通过。
- 原40例只读审计：`20261103T061305792004Z_NOA50-source-existing40-entry-audit_b8fa9ccb`，exit0。

父负责统一仿真；本候选不叠L、不改正式基线或生产，不提交Git。
