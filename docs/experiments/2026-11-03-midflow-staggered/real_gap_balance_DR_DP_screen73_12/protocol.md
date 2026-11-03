# D1单项消融DR/DP：73/74，共12例短筛

2026-11-03 21:14（Asia/Shanghai）结果前登记，root授权jobs2并行D1 development jobs4。父D1源2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a保持不变。DR源`tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_reactive/native_rules.py`，SHA89a9299f0dd043600846f7e5d7239e68d079053a75e4d32e442f0619fbab6811，仅去future π；DP源`tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_phase_off/native_rules.py`，SHAcfd2ee27031dac3b0efc2ef098551131878055b2518dfa4f9264a50886b4b86f，仅将局部phase_speed设0，横向主动组织/关系flags保留，**不是原纯NOA，也不是去掉全部交错**。两版各4项适用合同绿、1项不适用skip，不能称5项全过。

DR/DP × 每道1500/1750/2000辆/h × 73/74 × lane_drop × transform，共12例，180秒连续Bernoulli请求、500秒物理上限，jobs2、单例墙钟1200秒、外层3600秒。两源分开冻结，物理/道路/0.1秒步长/1秒变道/巡航28.8/最高33.3m/s/入口/CTH安全/NoA容量不变；九个非规则源仍旧runner固定BASE177f7a32088fb69efcc94d9acb72863e7e00e787。生产S不改，最终91–95禁启动。

主参考复用`20261103_midflow_D1_screen73_6`父D1同输入六例，正式DR减D、DP减D；不重跑D1，不混成组合候选。完整12例结束才判断机制差异，碰撞/失败/未完成/无改善/燃油代价全留。

```powershell
python -B scripts/run_logged.py --label midflow-DR-DP-screen73-12 --timeout 3600 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate DR=tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_reactive/native_rules.py DP=tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_phase_off/native_rules.py --stage midflow_DR_DP_screen73 --flows 1500 1750 2000 --seeds 73 74 --scenarios lane_drop --modes transform --duration 180 --max-time 500 --jobs 2 --worker-timeout 1200 --output tmp/staggered_bottleneck/20261103_midflow_DR_DP_screen73_12
```

全部raw完整保留待future π/phase/post5/实际几何及局部触发匹配审计，至少73三档DR/DP六例长期完整保留，收口前不提前清理，失败不删。旧批/manifest/seal/旧工具只读，Git由root执行。

```powershell
python -B scripts/run_logged.py --label midflow-DR-DP-screen73-primary --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_D1_screen73_6 tmp/staggered_bottleneck/20261103_midflow_DR_DP_screen73_12 --reference D --output docs/experiments/2026-11-03-midflow-staggered/real_gap_balance_DR_DP_screen73_12/analysis_primary
```

正式只取DR-minus-D_transform及DP-minus-D_transform各六对，工具缺D/noa配对保留可见但不用于评价。完整请求系统时间为主，另列行程/入口/燃油/瓶颈段/变道/0-1，种子等权。原[100,600)formal窗不足保留空值，机制共同[30,180)与post5单列，不补值、不称道路容量，不把phase-speed-off误称非编队。控制只读本车/有限局部观测/自身记忆。
