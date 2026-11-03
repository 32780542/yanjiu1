# 中流量交错控制固定基线：71/72，24例

2026-11-03 18:22（Asia/Shanghai）登记，性能结果产生前固定。此阶段仅研究每上游车道1500、1750、2000辆/h；不得把旧2250/2500试验纳入本阶段选择。截止2026-11-03 24:00。本批先建立现生产S与共同NOA的可复核基线，后续候选另行登记，不能回写本批。

## 固定输入和公平比较

- 三流量 × 种子71、72 × straight3与lane_drop（3→2）× noa与transform，共24例、12同输入配对。
- 600秒连续Bernoulli请求需求，统一1200秒物理上限；不用初始车辆覆盖，不修改输入请求。相同flow/seed/scenario的两模式必须通过原工具的需求、参数和非规则源核对。
- S规则461行，锁定SHA256 `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`。两模式都冻结这份规则文件，由原mode开关进入NOA或S；NOA容量不调参。
- 其余九个运行/配置文件沿用旧runner固定提交 `177f7a32088fb69efcc94d9acb72863e7e00e787`。原道路、入口、安全、积分步长0.1秒、巡航28.8和最高33.3m/s保持原物理合同。生产源、旧批、旧工具只读。
- 控制器只读本车、有限局部观测与自身记忆；不增加通信、真实ID优先权、车型真值、全局槽位或中心调度。
- 最多并发2例，单例墙钟1800秒，外层墙钟7200秒。墙钟限制只限定计算，不当作道路排空时间。每例完整结束后才判断安全、排空、指标或失败，不拿运行中部分数据排名。

## 执行入口

工作目录 `D:/yanjiu1/keyan1`。独占新raw目录 `tmp/staggered_bottleneck/20261103_midflow_baseline71_24`，旧尝试不动；中断后先检查进程、独立操作日志、manifest及case_record，不盲目重启同批。

```powershell
python -B scripts/run_logged.py --label midflow-baseline71-24 --timeout 7200 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate S=variants/phase5g_pure_formation/noa/native_rules.py --stage midflow_baseline71 --flows 1500 1750 2000 --seeds 71 72 --scenarios straight3 lane_drop --modes noa transform --duration 600 --max-time 1200 --jobs 2 --worker-timeout 1800 --output tmp/staggered_bottleneck/20261103_midflow_baseline71_24
```

旧runner逐例调用run_logged并冻结源码；旧seal逐例完成原件SHA/选定字段、ledger重构、离线再验。先保留所有完整positions/events，再按下述范围清理，不能给runner整体传`--prune-raw`。历史同档600秒个例墙钟约120秒；按2并发估计全批10–25分钟（含封存，运行状态以日志为准）。

```powershell
python -B scripts/run_logged.py --label midflow-baseline71-analysis --timeout 1800 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/summarize.py --batch tmp/staggered_bottleneck/20261103_midflow_baseline71_24 --reference S --output docs/experiments/2026-11-03-midflow-staggered/baseline71_24/analysis
```

## 评价和证据

主指标沿用完整请求系统时间，并列路内行程、真实入口等待、燃油、640–1100米段、800–1000米实际密度/均速/低速积聚、1000米越线流量、原0/1参与与持续时间。原[100,600)固定窗口、低速5m/s、原完整性门禁保持；差值S减NOA，逐种子和两种道路均保留，均值种子等权。固定窗口越线数不称容量，参与人数不称单支编队大小。任何碰撞、未完成、无改善、执行故障留在预定矩阵，不补值或隐去。

至少永久保留lane_drop、seed71、三流量、NOA/S两模式共6例完整positions/events供变道发生坐标、制动及瓶颈机制审计。所有case的input/result/trips和冻结源、封存bundle、车辆/区域/gate ledger完整保留。其余成功raw只有在原件验封、离线重验、机制证据提取完成且可恢复后才调用旧prune_raw精确清理两个原轨迹文件；失败/未完成/验封失败raw不清理。完整raw索引记录实际路径、字节数、SHA、保留/删除原因。选定字段紧凑证据不冒称可恢复全部原始轨迹。

Git由root统一执行。本任务不修改生产、旧工具或旧实验记录。
