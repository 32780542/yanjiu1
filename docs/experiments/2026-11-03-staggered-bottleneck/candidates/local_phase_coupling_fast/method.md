# J2fast：等价计算优化及验收

父代理已批准本设计。固定J2 SHA `895c263f471772482551ea695bc8071e28ad076753cc093762f09a3a43a15689`，原J2、E、生产和旧证据只读，不提交Git。

- [x] 在优化源产生前保存10000个有效有限局部state的J2输出oracle与等价测试，包含三个实测帧、横移、640/1000边界、前后远车、同x、三模式和完整Command/Memory/safe_speed；浮点按hex逐位比较，不写call-count红灯。
- [x] 新build只改safe_speed的无关dx早过滤与本车三道占用复用，以及_fill同call/同快照的cf_speed缓存。保持候选遍历、min/sum顺序、停止位置与CF公式；不缓存相位，不增加驾驶门槛或持久状态。
- [x] 分批核对10000 oracle、原225+37内存迁移、相同三个实测帧前后输出与计算耗时。没有输出差异，不加容差。
- [x] 确有计算收益后，独立冻结oldJ2/fast各跑同输入30秒需求SUMO一例，保留原件；解压positions及trips逐字节相同。这是重构验收，不纳入交通性能样本。

等价理由：_occupies只读当前有限物理值，先判断0<dx<=200不会改变任何参与停止位置min的front；本车占用元组保持原0/1/2顺序。cf_speed为同完整快照的纯函数，唯一局部track只作为当前call缓存键；before字典只属于一个observed，after字典只属于一次明确的moved快照，绝不跨车辆决策或跨帧复用。

## 冻结身份与逐函数范围

新源 `tmp/staggered_bottleneck/candidates/local_phase_coupling_fast/native_rules.py`，SHA `03ce8f468bdce13b9db82b7122eeeeb3d688128f3c3c5bb9dd34ab62df28c6a6`，450行，相对441行J2有效增加8行（另1空行）。[build.py](build.py)检查固定父SHA、优化前oracle已存在、AST只变 `_fill/safe_speed`，反向替换可逐字恢复J2。[native_rules.patch](native_rules.patch)及[source.json](source.json)保留明确差异。

`safe_speed`先排除原本不参与min的dx，再按原0/1/2顺序计算本车占道元组。仍对原顺序的front计算完全相同的free、sqrt、响应速度、stopping与min；没有改变安全公式、净距、200m范围或横移外推。

`_fill`只增加当前observed的before_speeds及每个明确after快照的after_speeds。唯一local track为纯缓存键，不参与优先级。预算先算过的目标后车，其后成本sum复用同一cf_speed值；所有affected次序、减法/max/sum次序、候选score及选择均保留。cf_speed、_front_following、_phase、_pair_error、_following、_decide和Memory未改，也不添加matches/clear缓存。

## 先存oracle，再改实现

[等价测试脚本](../../tests/test_local_phase_coupling_fast.py)先对原J2保存10000组输入和预期，再允许build。406组来自既有100/180/250秒真实帧的每个ego，其余为固定随机种子的有限typed states：唯一track、合法lane、0至MAX速度，包含横向运动、同x跨道、640/1000两侧、0/200m边界及远前/后车、不同自身Memory。它们用于计算等价，不作为随机交通分布。

Oracle为 `tmp/staggered_bottleneck/J2fast_oracle_20261103/oracle.jsonl.gz`，SHA `a24adc6bee09319fd1d71eb05c468be76bed54b41d9dd8e55caa43731fbe91f6`。每组都对noa/formation/transform检查完整Command和Memory，再单独检查safe_speed；用float.hex比较包括符号零的浮点表示，不用容差。四个2500组批次合计 **30000完整决策及10000安全速度精确相同**。

原225项精确14文件加既有J2迁移patch的内存运行也 **225项、37子测试全过**，原tests及历史H/P冻结比较保持。报告为[实现回归JSON](../../implementation/J2fast_core14_migrated.json)。

## 相同三个实测帧的计算比较

新复制profiler为 `tmp/staggered_bottleneck/profile_rules_J2fast_frames.py`，每版每帧各一次，输入/空自身Memory/局部dx[−100,+200]与原profiler一致。原profile及旧pstats未覆盖；所有三帧的输入输出也已包含在oracle中精确验证。

| 帧及车辆数 | J2墙钟s | J2fast墙钟s | 墙钟减少 | J2 response_cost累计s | fast response_cost累计s |
| --- | ---: | ---: | ---: | ---: | ---: |
| 100s，113车 | .059735 | .049890 | 16.5% | .003350 | .001351 |
| 180s，179车 | .214829 | .173000 | 19.5% | .012375 | .005019 |
| 250s，114车 | .726540 | .293505 | 59.6% | .596826 | .186562 |

250秒帧cf_speed调用由2006降到1597，_occupies调用743628降到198057；这只是热点解释，不是用call-count代替等价合同。以上计时包含cProfile开销、机器同时有正式批次，不能直接宣称GUI实际提速幅度。原始六份pstats/文本/完整JSON在 `tmp/staggered_bottleneck/J2fast_computational_profile_20261103/`。

## 真实SUMO精确对照

新批 `tmp/staggered_bottleneck/20261103_J2fast_equivalence30_2`：同flow2500、seed4、lane_drop、transform，30秒需求、150秒排空上限、oldJ2/fast各一例。独立runner冻结各自真实源码；input除 `source_sha256/noa/native_rules.py` 外全部字段逐字结构相同。原件保留，未prune。

两例各59/59安全排空，碰撞/teleport=0。**734帧、26014车帧的解压positions全部逐字节相同**；完整trips.json及解压trips.jsonl也逐字节相同，包含数值、横移事件、0/1、tripinfo燃油/时间。解压positions SHA `cb5b2686f760aa54b9b1a4641117c91b3f2970cb0fdab2fa715041bc04875ec7`。这两例不加入正式交通样本，也不能把旧J2的原600秒seed4称作已由fast重跑。

[verify.py](verify.py)把oracle四批、核心回归、profile保护源、原输入和三份实测文件重新联合核对，结果保存在[verification.json](verification.json)。

## 操作记录

- 优化前10000 oracle：`20261103T052107767555Z_J2fast-freeze-original-oracle10000_96058a3c`，exit0。
- 固定源构建：`20261103T052145545187Z_J2fast-pure-computation-build_6a3d099a`，exit0。
- 四批oracle等价：`20261103T052205612348Z_J2fast-equivalence-0-2500_41fd64ca`、`20261103T052205650017Z_J2fast-equivalence-2500-2500_d01deb4b`、`20261103T052205662157Z_J2fast-equivalence-5000-2500_b460c63a`、`20261103T052205650017Z_J2fast-equivalence-7500-2500_db5ba6a7`，均exit0。
- 三帧profile：`20261103T052247680711Z_J2fast-three-recorded-frame-profile_59f5400a`，exit0。
- 225+37核心：`20261103T052247682714Z_J2fast-core14-J2-migration_aa6a6628`，exit0。
- 两例真实SUMO：`20261103T052344008899Z_J2fast-real-equivalence30-two-cases_a7f8a02f`，exit0。
- 联合原件核验：`20261103T052625941703Z_J2fast-joined-oracle-core-real-trace-verification_7fa39a96`，exit0。

此单元无输出不一致失败，没有改变驾驶公式或测试预期来通过；没有Git提交或生产修改。
