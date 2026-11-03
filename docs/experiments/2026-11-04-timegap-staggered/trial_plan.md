# 锁源实验与完成状态

工作目录 D:/yanjiu1/keyan1；研究截止仍为北京时间 2026-11-04 08:00。
用户取消的是“最后发车后30秒形成/10秒保持”验收期限。

## 已锁定来源

- 主方法 C12_200/300：tmp/staggered_bottleneck/candidates/20261104_C12_200/native_rules.py；300 同模式路径。
- 匹配平行对照 P12_200/300：对应 20261104_P12_200/300 路径。
- 四源均316行，路径及已交付 SHA 在 stage/formal_protocol_600.json；04:35:21 登记，首批约04:36启动。
- C12 修复真实纵向前驱被替换时不应仅因 track 不同而断链；不增加字段、路区、阈值。
- root 已锁定控制，正式结果不再用于改算法；fallback final_C8 不作正式别名。
- 200/300仅 ROAD_PREVIEW 不同；h=.85，CRUISE=28.8，MAX_SPEED=33.3；共同物理、入口、安全层不改。
- 单车仅用有限局部观测与自身记忆，不引入 D1 负荷均衡、成本排名或中心调度。
- root统一安装、Git与push；不建worktree/fullcopy。旧尝试目录与raw只读。

## 正式顺序

| 新批次后缀 | 来源 | 道路 | 模式 | 例数 |
|---|---|---|---|---:|
| main_drop_211_215_r01 | C12_200/300 | lane_drop | noa/formation/transform | 90 |
| main_straight_211_215_r01 | C12_200 | straight3 | noa/formation/transform | 45 |
| parallel_drop_211_215_r01 | P12_200/300 | lane_drop | transform | 30 |
| parallel_straight_211_215_r01 | P12_200 | straight3 | transform | 15 |

完整批名均以 20261104_formal600_ 开头，目录在 tmp/staggered_bottleneck 下。
固定 flow1500/1750/2000 veh/h/道，seed211/212/213/214/215，600 s发车、1200 s最大仿真。
先完成 main135 并一次消费，再运行 parallel45；各批顺序，池 jobs3，不叠加另一个池。
root 长流开发 NOA 单 job 与本池合计最多4；不由本组代管、不重跑该基线。
worker-timeout1800 s、外层 run_logged 上限7200 s。所有raw保留，不传 --prune-raw。

## 复用入口

旧 runner：docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py。
冻结177f7a3的十个运行/配置文件，仅 NAME=path 替换规则。

    python -B scripts/run_logged.py --label timegap-formal600-main-drop-211215 --timeout 7200 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate C12_200=tmp/staggered_bottleneck/candidates/20261104_C12_200/native_rules.py C12_300=tmp/staggered_bottleneck/candidates/20261104_C12_300/native_rules.py --stage formal600_main_drop --flows 1500 1750 2000 --seeds 211 212 213 214 215 --scenarios lane_drop --modes noa formation transform --duration 600 --max-time 1200 --jobs 3 --worker-timeout 1800 --output tmp/staggered_bottleneck/20261104_formal600_main_drop_211_215_r01

其余批次只按表调整 candidate/scenario/mode/stage/output。重试必须新后缀。
断流先查已有进程/manifest/log，不把未收到最终消息当方法失败，不盲目重启。

## 必要消费

复用旧sealed-case evaluator，tools/report_trial.py支持显式 TARGET/MODE=REFERENCE/MODE，按scenario与目标mode分别分组。
main分别报 transform−NOA、formation−NOA、transform−formation；parallel报 P12 transform−C12 transform，同preview/同需求。
300缩道的DID显式共享200直路的同模式/同几何实际case，并保留真实reference candidate，不重复计独立样本。
道路DID按同flow/seed先算再等权平均；五个种子的全部方向同时保留，不按跨道路/模式池化。
主指标并列系统时间、路内时间、入口等待、fuel；不作单一成本排序。
固定区域窗沿用[100,600)，不换窗，不以完成子集填补未完成效率。
形成直接0/1与实际D(v)几何分开；实际LC位置/单车最大LC、超过两次车辆数从已读trips描述。
安全、未完成、负向、实现异常与封包失败全部保留；不新建审计器，不重复旧验证。

## 已完成开发入口

C8_dev600_summary.md：原C8的54例持续开发，三模式/两道路；旧flag一处记录遗漏仅作历史，不据其参与率选参数。
C8_joint03_dev180_summary.md、C8b_P8b_dev180_summary.md：相位去门/参数试验及交通代价。
C11_P11_dev180_summary.md：24例安全排空，但C11几何仅38/44交替，不采用。
C12_P12_dev180_summary.md：24例安全排空，C12对NOA12/12时间改善、对C8全慢、对C11全快；完整正负表。
更早各候选/直路归因在对应summary；C6含已修bug，C10的11异常/1完整与C10b的43/44未采用结果独立保留。

## 当前完成状态与固定事后组

正式main135与matched parallel45已全部安全排空/消费，源仍锁定；见formal600_main_summary.md与formal600_parallel_summary.md。
扩展NOA_front20045已完成，见posthoc_NOAfront200_summary.md；共同请求cap28.8组36已完成，见posthoc_speedcap288_summary.md。
h=.75/1.00敏感性48正整组运行（200信息、两道路、201/202、NOA/T、600/1200、独立MAX33.3），不据结果改变主参数。
事后源/顺序/同输入引用与时间决定见stage/posthoc_protocol_600.json；所有raw保留，08:00工作截止不变。
