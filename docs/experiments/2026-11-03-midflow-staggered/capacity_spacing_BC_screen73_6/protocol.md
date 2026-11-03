# 容量参考匹配非交错BC短筛：73/74，6例

2026-11-03 20:24（Asia/Shanghai）结果前登记，root授权jobs2。BC源`tmp/staggered_bottleneck/candidates/midflow_capacity_spacing_control/native_rules.py`，429行，SHA256 `b25f0047ebe6b8989607bd9c7c94ce10e7579e495e300f00f7d7fda189889f35`；B父源与旧尝试不改。

BC保留B同45/90的基础CTH几何关联，移除phase/freefill，普通超车开启，ownflag全0；NoA自身mode仍与S bitexact。它是同容量参考无主动交错的匹配控制，**不是原纯NOA**，不叠GP/V/F/C5。设计密度匹配不称实测道路容量。

每道1500/1750/2000辆/h、73/74、lane_drop、transform、180秒连续Bernoulli请求、500秒物理上限，共6例，jobs2、单例墙钟1200秒、外层3600秒。九个非规则源由旧runner固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`，原物理/道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/SUMO安全/NOA容量不变，生产不改，最终91–95未锁源前禁启动。

主参考复用已完整结束的`20261103_midflow_B_screen73_6`六例B，源SHA `7d749ba8919efbf06efc0abd43846dee4c13b886e81019ae89c0f0116a1553d2`，正式差值BC减B，不重复B；S旧六例可单独作次比较。全6完成后才评价，碰撞/未完成/执行失败/无改善/燃油代价全部保留。

```powershell
python -B scripts/run_logged.py --label midflow-BC-screen73-6 --timeout 3600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate BC=tmp/staggered_bottleneck/candidates/midflow_capacity_spacing_control/native_rules.py --stage midflow_BC_screen73 --flows 1500 1750 2000 --seeds 73 74 --scenarios lane_drop --modes transform --duration 180 --max-time 500 --jobs 2 --worker-timeout 1200 --output tmp/staggered_bottleneck/20261103_midflow_BC_screen73_6
```

新raw全部完整保留待容量参考/非交错/实际制动/post5匹配审计，至少73三例长期全raw保留；其他成功case仅在原件/完整紧凑包/隔离离线验核及机制明确放行后精确清理，失败不删。旧批及原manifest/seal只读，Git由root统一处理。

```powershell
python -B scripts/run_logged.py --label midflow-BC-screen73-primary --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_B_screen73_6 tmp/staggered_bottleneck/20261103_midflow_BC_screen73_6 --reference B --output docs/experiments/2026-11-03-midflow-staggered/capacity_spacing_BC_screen73_6/analysis_primary
```

主分析仅取`BC-minus-B_transform`六对，原工具缺B/noa配对保持可见但不使用；次对S另目录。主指标完整请求系统时间，另列行程/入口/燃油/瓶颈段/变道/0-1，种子等权。原[100,600)formal窗不足照留空值，共同[30,180)机制窗/post5另列，不补值、不称容量、不把参与人数称单支编队大小。控制只用本车/有限局部观测/自身记忆。
