# 2026-11-04 时距交错：实验调度页

工作目录 `D:/yanjiu1/keyan1`；截止北京时间 2026-11-04 08:00。本页只复用旧工具，不改生产代码、不另建 worktree/full copy。
已读根 AGENTS 与 STS；旧尝试只读。候选路径由主代理给出后才启动；正式 seed 211–215 在规则锁定后才用。

## 固定输入与候选身份

- 只测每道 1500/1750/2000 veh/h；共同 `HEADWAY=.85`、`CRUISE=28.8`、`MAX_SPEED=33.3`。
- 主矩阵是 `lane_drop` 的 ROAD_PREVIEW=200/300 m 两种道路观察条件；200 m 无额外警示，300 m 统一警示。
- 同一 A/B 规则族的 200/300 文件仅道路可见范围常量不同。A/B 具体形状机制及文件名由主代理登记。
- 共用反应式 NOA：跟驰、普通受阻超车、可见末端约束、安全间隙接受；不做 gap 中点对齐或组织式补位。
- A/B 的 NOA 分支确认完全相同后，每种 preview 只运行 A 的 NOA，作为 A/B 主比较参考，避免重复仿真。
- 旧提前 NOA/旧 D1/S 只作附加参考；不混入本轮主样本、开发或正式种子统计。
- 若主代理要求区分一般直路组织收益，再为入选版本加 `straight3` 同输入配对；不预先扩大筛查矩阵。

## 复用入口与源契约

`docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py` 从 `177f7a3` 冻结十个运行/配置文件，`NAME=path.py` 只替换 `noa/native_rules.py`。
候选须保留旧引擎导入的 `Vehicle, Memory, decide, safe_speed` 及 Command 字段；`Memory()` 可空构造，`formation_state` 严格为 int 0/1。
旧引擎仍传入真实 `drop_x`，新规则必须先在内部裁剪道路观测，再做任何分支；不改物理、原生入口、GUI 或安全层。
所有输出均是新的 `tmp/staggered_bottleneck/20261104_*` 目录，不传 `--prune-raw`。raw、失败和反向结果全部保留。
旧 runner 自带封包流程可直接运行；不叠加新的哈希清单或验证循环。总结只调用实际消费数据所需的既有接口。

## 顺序与数量

| 阶段 | seeds | demand/max-time(s) | 每个 preview | 总数 |
| --- | --- | --- | --- | --- |
| 开发短筛 | 201,202 | 180/600 | A/B transform 各6 + 共用NOA6 | 36 |
| 入选持续 | 201,202 | 600/1200 | 入选transform6 + 同源NOA6 | 24 |
| 锁源正式 | 211–215 | 600/1200 | 入选transform15 + 同源NOA15 | 60 |

600 s 持续阶段先完成再决定锁源；有失败仍保留记录。未明确锁源不执行正式。若 A/B NOA 不同，不复用，先由主代理统一共用基线。
180 s 用于安全、排空、主旅行指标和机制筛查；固定区域窗仍为 [100,600)，不足完整窗的正式区域指标保持 null，不当容量证据。

## 可直接填写的 PowerShell 命令

以下变量中的候选路径须替换为主代理交付文件；命令模板不表示已经运行。每次重试更新 r01 后缀。

```powershell
$Tools='docs/experiments/2026-11-03-staggered-bottleneck/tools'
$Stage='docs/experiments/2026-11-04-timegap-staggered'
$P=200  # 完成后以300再执行；ROAD_PREVIEW由源文件定义，runner没有此参数
$A="A$P"; $B="B$P"
$AFile="$Stage/candidates/$A.py"; $BFile="$Stage/candidates/$B.py"
$Base="tmp/staggered_bottleneck/20261104_dev180_p${P}_noa_r01"
$Trial="tmp/staggered_bottleneck/20261104_dev180_p${P}_AB_r01"
python -B scripts/run_logged.py --label "timegap-dev180-p${P}-noa" --timeout 3600 -- python -B "$Tools/runner.py" --candidate "$A=$AFile" --stage dev180 --flows 1500 1750 2000 --seeds 201 202 --scenarios lane_drop --modes noa --duration 180 --max-time 600 --worker-timeout 1200 --jobs 4 --output $Base
python -B scripts/run_logged.py --label "timegap-dev180-p${P}-AB" --timeout 5400 -- python -B "$Tools/runner.py" --candidate "$A=$AFile" "$B=$BFile" --stage dev180 --flows 1500 1750 2000 --seeds 201 202 --scenarios lane_drop --modes transform --duration 180 --max-time 600 --worker-timeout 1200 --jobs 4 --output $Trial
python -B scripts/run_logged.py --label "timegap-dev180-p${P}-summary" --timeout 1200 -- python -B "$Tools/summarize.py" --batch $Base $Trial --reference $A --output "tmp/staggered_bottleneck/20261104_dev180_p${P}_summary_r01"
python -B scripts/run_logged.py --label "timegap-dev180-p${P}-pairedB" --timeout 1200 -- python -B "$Tools/report_paired.py" --batch $Base $Trial --baseline $A --target $B --output "tmp/staggered_bottleneck/20261104_dev180_p${P}_pairedB_r01"
```

持续/正式直接复用 runner 命令：入选候选单独 `--modes noa transform`，duration/max-time 改 600/1200；持续 seeds=201 202，正式 seeds=211 212 213 214 215。
输出分别用 `20261104_dev600_p{P}_{candidate}_r01` / `20261104_final600_p{P}_{candidate}_r01`；外层 timeout 7200、worker-timeout 1800，jobs 4。
同一 candidate/flow/seed/scenario/mode 在多 batch 重复时，summarize 会拒绝；因此短筛、持续、正式分别总结，不合并重复身份。

## 决策与报告口径

主指标并列：系统时间、路内旅行时间、入口等待、fuel g/km；逐 seed 配对差和等权汇总均保留，不以单一成本排名取代机制判断。
安全/排空/未完成/封包失败按原状态报告，不能把不合格 case 悄悄丢弃。200/300 分开主表，跨范围差异不冒称纯结构收益。
形成用直接 0/1 统计；它不等于单队规模，也不替代真实 D(v)=4+1.5+.85v 的几何恢复。
机制优先复用 raw/trips 的实际换道请求/完成位置，检查队尾在瓶颈后是否恢复交错与动态间距；不要只画理想格点。
已有 evaluator 的 `per_case.csv/paired.csv/summary.json` 与 `report_paired.py` 的逐种子/等权表供主代理汇总；root 统一 Git/push。
