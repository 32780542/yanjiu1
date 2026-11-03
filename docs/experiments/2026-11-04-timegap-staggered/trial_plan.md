# C8持续开发与正式前计划

研究工作目录 D:/yanjiu1/keyan1；工作截止仍为北京时间2026-11-04 08:00。
用户取消的是“最后发车后30秒形成/10秒保持”的形成验收窗口，不是研究截止。
原317行C8为当前生产及持续开发基准：延长观察从70 s起全45车交替、44/44持续到109.1 s首次离场，392帧；100 s半D MAE=.000328 m，22次LC且无重复。
54例消费已完成；因道路上形成相位成熟度仍须独立检验，另做joint03去旧方向门的12例短筛，结果与交通代价并列，最终控制尚未锁定。
04:15锁定前最后四源C8b/P8b（phase .6/raw限±5）24例已完成，48个配对合格，见C8b_P8b_dev180_summary.md；无正式。
最后形成拓扑C11/P11四源317行已冻结，24短例180/600用jobs2（root长NOA1+几何1合计4），04:25前据完整结果锁最终控制；正式仍未揭。
root单job长NOA1800/2700仅开发201/202、两preview三flow12例，后续长主法配对复用，不重跑该NoA；不由本组代管。
C9/C10b不继续叠加；C10实现异常与C10b未达全链的结果独立保留，见对应summary。

## 固定控制与输入

- 冻结源：tmp/staggered_bottleneck/candidates/20261104_forward_gap_C8_200/native_rules.py；C8_300同目录模式。
- 200/300仅ROAD_PREVIEW不同；h=.85，CRUISE=28.8，MAX_SPEED=33.3；不改共同物理、原生入口或安全层。
- 只测1500/1750/2000 veh/h/道；开发seed201/202。
- 正式seed211–215仍未揭；规则锁定及主代理明确指示后才运行，不提前借正式结果改规则。
- 单车只用有限局部观测与自身记忆，不引入D1负荷均衡、成本排名或中心调度。
- root统一安装、Git与push；不建worktree/fullcopy。旧尝试目录与raw只读。
- 当前54例仍为原C8，已知50–200 m闭孔实际reference的linked有一行记录遗漏；控制动作不受影响，旧flag仅开发历史，不据参与率调参。正式/主报告拟用状态补正版C8S，尚未启动。

## 当前54例持续开发

| 批次 | 候选 | 道路 | 模式 | seeds/flows | demand/max-time | 例数 |
| --- | --- | --- | --- | --- | --- | ---: |
| drop r01 | C8_200、C8_300 | lane_drop | noa/formation/transform | 201/202；三流量 | 600/1200 s | 36 |
| straight r01 | C8_200 | straight3 | noa/formation/transform | 201/202；三流量 | 600/1200 s | 18 |

旧runner不能对两个候选指定不同道路集合，因此拆成两个新批顺序执行，总jobs=3；root安装/烟雾留一个资源。
worker-timeout=1800 s、外层run_logged硬上限7200 s；所有raw保留，不传--prune-raw。
drop 36例与straight 18例均全安全排空/封包，统一一次消费已完成；结果见C8_dev600_summary.md。joint03短12例亦已完成，见C8_joint03_dev180_summary.md；正式未启动。

## 复用命令

从仓库根目录执行；旧runner冻结177f7a3的十个运行/配置文件，只用NAME=path替换规则文件。

    python -B scripts/run_logged.py --label timegap-C8-dev600-drop-201202 --timeout 7200 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate C8_200=tmp/staggered_bottleneck/candidates/20261104_forward_gap_C8_200/native_rules.py C8_300=tmp/staggered_bottleneck/candidates/20261104_forward_gap_C8_300/native_rules.py --stage C8_dev600 --flows 1500 1750 2000 --seeds 201 202 --scenarios lane_drop --modes noa formation transform --duration 600 --max-time 1200 --jobs 3 --worker-timeout 1800 --output tmp/staggered_bottleneck/20261104_C8_dev600_drop_201_202_r01

    python -B scripts/run_logged.py --label timegap-C8-dev600-straight-201202 --timeout 7200 -- python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/runner.py --candidate C8_200=tmp/staggered_bottleneck/candidates/20261104_forward_gap_C8_200/native_rules.py --stage C8_dev600 --flows 1500 1750 2000 --seeds 201 202 --scenarios straight3 --modes noa formation transform --duration 600 --max-time 1200 --jobs 3 --worker-timeout 1800 --output tmp/staggered_bottleneck/20261104_C8_dev600_straight_201_202_r01

重试必须用新后缀；断流先看已有进程/manifest/log，不把未收到最终消息当方法失败，也不盲目重启。

## 必要消费

复用旧sealed-case evaluator，tools/report_trial.py仅扩实际所需接口：显式TARGET/MODE=REFERENCE/MODE、目标mode与scenario分别分组。
两preview分别输出transform−NOA、formation−NOA、transform−formation；不把两道路或两目标模式均值混合。
600 s只消费本轮新需求，不能拿180 s旧NoA作600 s参考；跨道路DID按同flow/seed先算再等权平均，并保留实际参考身份。
主指标并列系统时间、路内时间、入口等待、fuel；不作单一成本排序。固定区域窗沿用[100,600)，不换窗、不填补不完整指标。
形成直接0/1与真实D(v)几何分开；实际LC完成位置/单车最大LC、超过两次车辆数从原已读trips描述，不能以flag高替代全链恢复。
安全、未完成、负向结果、实现异常及封包失败全部保留，拒绝配对也输出；不新建审计器或重复旧验证。

## 历史入口

180 s各候选与直路归因分别在A/B/C/C2/C3/C4/C5RG/C6/C7/C8/C9/C10b对应summary中，原raw均保留。
C6标记为含远孔速度基准bug历史；C7是一行修复后独立复验，不继承C6效率判断。
C10_implementation_error_summary.md保留11异常/1完整、一次实际末帧重放与旧封包器末帧错位；不以异常C10作效率对照。
C10b_dev180_summary.md保留正常交通正负结果及43/44几何不采用结论。正式前不重跑这些旧批。
