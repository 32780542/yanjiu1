# GP2匹配非编队G0短筛：73/74，6例

2026-11-03 20:13（Asia/Shanghai）结果前登记，root授权即刻jobs2，与GP2 development600 jobs2合计4模拟。G0源`tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_G0/native_rules.py`，501行，SHA256 `4562f5c187d1731671e925f66f5619ea4f1357efa1c5ea9e624901c8d179fa43`。

G0从冻结GP2只改_decide，关闭phase与freefill、formation_state全部0，保留普通NoA慢前车超车；实际真实gap规划、CTH兼容带、执行和物理同GP2。运行mode为transform，标签为匹配非编队控制，**不是原纯NOA**。用来检验主动交错子系统与局部规划自身的差异，不叠F/V/C5或密度缓冲候选，生产不动。

每道1500/1750/2000辆/h、73/74、lane_drop、transform、180秒持续Bernoulli请求、500秒物理上限，共6例。jobs2、单例墙钟1200秒、外层3600秒。原runner九个非规则源固定BASE `177f7a32088fb69efcc94d9acb72863e7e00e787`，原物理/道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/SUMO安全/NOA容量不变。最终91–95未锁源前禁启动。

主参考直接复用`20261103_midflow_GP2_screen73_6`中的GP2六例，规则SHA `37306e86a8e0e1045763bf54ebb3adca60ebc489dde6925a61553240ad0195cc`。正式差值G0减GP2，不重复GP2。可另对原S六例作次要比较，不能把G0称NOA或把该对照当只关闭单一phase项。

```powershell
python -B scripts/run_logged.py --label midflow-GP2-G0-screen73-6 --timeout 3600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate G0=tmp/staggered_bottleneck/candidates/midflow_bound_real_gap_G0/native_rules.py --stage midflow_GP2_G0_screen73 --flows 1500 1750 2000 --seeds 73 74 --scenarios lane_drop --modes transform --duration 180 --max-time 500 --jobs 2 --worker-timeout 1200 --output tmp/staggered_bottleneck/20261103_midflow_GP2_G0_screen73_6
```

全6结束后才评价，碰撞/未完成/失败/无改善均保留。全部raw先完整保留待同entrant/receiver、入窗、post5机制审计，至少seed73三例全positions/events长期保留；其他成功case须原件/完整紧凑包/隔离离线复核及机制明确放行后才精确清理，失败不删。原GP2与旧批/manifest/seal只读，Git由root统一处理。

```powershell
python -B scripts/run_logged.py --label midflow-GP2-G0-screen73-primary --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_GP2_screen73_6 tmp/staggered_bottleneck/20261103_midflow_GP2_G0_screen73_6 --reference GP2 --output docs/experiments/2026-11-03-midflow-staggered/matched_GP2_G0_screen73_6/analysis_primary
```

主分析仅取`G0-minus-GP2_transform`六对；工具自动列出的缺GP2/noa配对保留可见，但不用于评价。次分析可用原S参考与`--reference S`，取G0减S六对，单独目录。完整请求系统时间为主，另列行程/入口/燃油/瓶颈段/变道/0-1，种子等权。原[100,600)formal窗不足照留空值，共同[30,180)机制窗及post5另列；不补值、不称容量、不把flag人数当单支编队规模。控制只用本车/有限局部观测/自身记忆。
