# J2既有三帧计算热点诊断

2026-11-03。只读取TM诊断中既有100/180/250秒帧，对固定E和J2每帧各计算一次，不启动SUMO、不改变任何驾驶源。新脚本为`tmp/staggered_bottleneck/profile_rules_J2_frames.py`，原`profile_rules.py`和`E_frame_profile.pstats`保留。operation `20261103T051239115633Z_J2-three-recorded-frame-computational-profile_962ba695`，exit0，3.219秒。

**主要热点是原_fill的反事实跟驰成本，并非J2相位公式。** 250秒密集帧中，J2的decide累计.6944秒，_fill .6437秒，response_cost .5713秒；E同帧decide也需.6848秒。只缓存_physical_phase不能解决这一帧的主要开销，本单元未构建J2fast。

## 可比输入和限制

输入来自`tmp/staggered_bottleneck/diagnostic2500_20261103/transform/20261103T031406911129Z_lane_drop_transform_s1_5390a4/diagnostic.jsonl.gz`。本车实车帧逐一转换，观测限定为本车dx[−100,+200]，每车使用新的空Memory，mode=transform。100/180/250秒分别113/179/114车。行观测构造计入整帧计时，与原E单帧脚本一致。

这些是TM轨迹帧和空记忆计算基准，不能代表J2自己轨迹、顺序执行记忆或GUI完整帧耗时；不能从本次计算成本推导交通收益。机器同时有正式批次运行，单次墙钟有调度噪声。保留process CPU和cProfile完整记录，不把微秒差异当可靠优化收益。

固定源：E `04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274`；J2 `895c263f471772482551ea695bc8071e28ad076753cc093762f09a3a43a15689`。两源、生产、原profiler及旧pstats均在运行前后SHA一致。

## 每帧耗时

单位秒；decide与内部函数为cProfile累计时间，不能相加，因为存在嵌套。

| 帧 | E整帧墙钟 | J2整帧墙钟 | E decide累计 | J2 decide累计 | J2 _fill累计 | J2 _following累计 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 100s，113车 | .052823 | .056111 | .051628 | .054928 | .034858 | .007406 |
| 180s，179车 | .155291 | .194244 | .152281 | .191235 | .125752 | .022689 |
| 250s，114车 | .686554 | .696156 | .684783 | .694354 | .643666 | .017421 |

_fill占J2 decide累计约63.5%、65.8%、92.7%。250秒车数少于180秒但费用更高，因为真正尝试的自由补位成本评估更多，不能用车数单独线性估算。

| J2内部调用 | 100s calls / 累计ms | 180s calls / 累计ms | 250s calls / 累计ms |
| --- | ---: | ---: | ---: |
| _pair_error | 1298 / 4.392 | 4483 / 14.272 | 3383 / 11.169 |
| _physical_phase | 2596 / 3.418 | 8966 / 11.364 | 6766 / 8.905 |
| _fill.matches | 2438 / 7.298 | 3325 / 16.156 | 1470 / 8.438 |
| _clear（含_fill外） | 59 / .545 | 571 / 7.898 | 692 / 14.323 |
| _fill.response_cost | 12 / 3.255 | 35 / 11.493 | 611 / 571.326 |
| cf_speed | 31 / 2.923 | 86 / 10.515 | 2006 / 544.070 |
| safe_speed（含最终硬限速） | 144 / 12.813 | 265 / 44.706 | 2120 / 540.958 |

250秒最昂贵路径为_fill→response_cost→cf_speed→safe_speed→走廊_occupies。_occupies共743628次、累计306.565ms。这条成本路径由E继承；E同帧也有2080次cf_speed、累计558.682ms。

## 最小建议，尚未实施

1. 若只优化J2新增计算，在单次_following内缓存每个当前实车的三道_physical_phase，仍按原`peer_phase−car_phase`运算顺序计算相位差。它最多消除本帧3.4/11.4/8.9ms的原累计调用费用，还要扣去建表/查询费用；即使理想全消除，也只相当于decide的6.2/5.9/1.3%，无法解释或解决250秒主要瓶颈。不要跨车辆决策持久缓存，也不要以track改变选择顺序。
2. _fill可先考虑同call的`matches(center,lane)`、`_clear(car,lane)`和每center的references缓存，严格保持原候选列表和遍历/打平局顺序。100/180秒matches有可见费用，250秒matches与全部_clear累计相加也只有22.8ms，且本次未度量重复key比例；不应预先宣称有明显收益。
3. 真正的大头是250秒反事实safe_speed。现有response_cost已经按(car.track,lane)缓存最终cost；本轮没有进一步修改cf_speed、安全模型或成本公式。若继续优化，应先单独证明同一完整输入的重复计算能否复用，而不是为提速删掉安全/补位评价或更改驾驶规则。本次授权下未实现这类改动。

原始六份pstats、六份top30文本及完整`profile.json`均保存在`tmp/staggered_bottleneck/J2_computational_profile_20261103/`。J2fast若获后续授权，应另建冻结身份并验证完整Command/Memory逐字相同；本报告只提供热点和开销上界，没有优化版性能结论。
