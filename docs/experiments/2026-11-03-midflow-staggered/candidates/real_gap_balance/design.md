# D：真实gap与未来资源负荷闭环选道

从固定Git S blob `1aa86344af2a269053cd4fcda9d58168697daf17:variants/phase5g_pure_formation/noa/native_rules.py`独立构建，SHA256须为`8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`。不叠加旧候选。

整段替换`_fill`的anchor/centers/matches/full格点策略。统计原可见组件内±90m实车；测得`abs(vy)>.1`时，以`y/3.3−.5`按运动方向ceil/floor投影到实际目的车道，夹到0..2，其余取实际lane。每车仅计一次。transform准备接收时以π(0)=0、π(1)=π(2)=1表示未来资源，其余按当前实际车道资源。

对未测得横移的实际存续道车辆，枚举相邻实际车道，仅保留计数平方和势能严格下降的转移。目标必须通过原8m clear，原`_merge_target`给出的真实gap目标离车不超过原GAP=30m。原response_cost公开CF损失及新后车单独制动上限保持。先最小响应损失，再前方几何破平局，只有本车为当前可见局部winner时输出本车车道。

gap/clear与响应损失均使用本车已可见observed，不补看其他候选私有视野。若本车胜出，之后原`_join_speed`用同帧同rows、初始空held重算同一真实gap，因此目标与执行绑定，不增加目标记忆。该性质不意味着其他候选的模拟响应等于它们自己的真实私有计算。

transform本车在准备区或±90m看见实际lane2车辆已进入公开准备段时开始未来2资源接收协调，并取消尚未开始的入lane2补位。lane2必要合流仍只在原准备区触发；NOA原样。实际纵向phase/CTH、安全层、加入执行和Memory字段不变。没有新增等待、门禁、增益或CTH接入阈值。

先TDD验证完整三车道层的未来负荷需要迁移而旧S/F2冻结；再检验上游接收、运动投影不双计、已平衡45/24m布局不迁移、目标/执行同gap、标签/排列/感知外、1000状态NOA与safe/coreCF精确不变。默认formation及直路使用新真实gap局部负荷策略，不能要求与S组织动作相同。交通结果由外部runner独立完成。
