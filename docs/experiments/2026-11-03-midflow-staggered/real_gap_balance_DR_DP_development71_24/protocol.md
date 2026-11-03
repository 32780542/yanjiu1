# D1消融DR/DP的600秒双道路development：71/72，共24例

2026-11-03 21:30（Asia/Shanghai）结果前登记，root授权jobs4，另并行D1长1800 jobs2。DR源89a9299f0dd043600846f7e5d7239e68d079053a75e4d32e442f0619fbab6811，仅去D1的future π；DP源cfd2ee27031dac3b0efc2ef098551131878055b2518dfa4f9264a50886b4b86f，仅phase_speed0，横向主动组织/关系flags保留，不能称NoA或去掉全部交错。两源分别位于tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_reactive及midflow_real_gap_balance_phase_off，父D1 2be889...1f35a保持冻结，不叠其它候选。

DR/DP×1500/1750/2000每道流量×71/72×straight3/lane_drop×transform，共24例，600秒持续Bernoulli请求、1200秒物理上限。主参考直接复用real_gap_balance_D1_development71_12同输入D1十二例，不重跑D1/S/NOA。jobs4、单例墙钟1800秒、外层7200秒，总6模拟已获授权。完整24矩阵后再判断phase/π的道路DID，短筛仅drop不能当该DID。

原runner九个非规则源固定BASE177f7a32088fb69efcc94d9acb72863e7e00e787；原物理/道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/SUMO安全/NoA容量保持。生产仍S，父源不改。碰撞/失败/未完成/小效应/负效应全部保留，最终91–95未获最终锁源授权前禁启动。

```powershell
python -B scripts/run_logged.py --label midflow-DR-DP-development71-24 --timeout 7200 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate DR=tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_reactive/native_rules.py DP=tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_phase_off/native_rules.py --stage midflow_DR_DP_development71 --flows 1500 1750 2000 --seeds 71 72 --scenarios straight3 lane_drop --modes transform --duration 600 --max-time 1200 --jobs 4 --worker-timeout 1800 --output tmp/staggered_bottleneck/20261103_midflow_DR_DP_development71_24
```

全部raw留待全量/post5/实际局部几何和触发审计，至少71缩道三档DR/DP六例长期全raw保留；收口前不提前清理，失败不删。新目录独占，旧批/manifest/seal/工具只读，Git由root负责。两消融各4适用合同绿+1不适用skip，不报5项全过。

```powershell
python -B scripts/run_logged.py --label midflow-DR-DP-development71-primary --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_D1_development71_12 tmp/staggered_bottleneck/20261103_midflow_DR_DP_development71_24 --reference D --output docs/experiments/2026-11-03-midflow-staggered/real_gap_balance_DR_DP_development71_24/analysis_primary
```

正式DR减D、DP减D同mode各12对；工具缺D/noa策略对保留可见但不用。DID为同种子消融差值缩道减直路，正值表示D1相对消融具有额外缩道节省。系统为主，并列行程/入口/燃油/瓶颈段/区域/低速/越线/0-1，原[100,600)完整性门禁保持，种子等权、不补值、不称容量。父D1十二例全raw仍在，新增post5可全量同父匹配。控制只用本车/有限局部观测/自身记忆。
