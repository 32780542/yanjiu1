# D1 理论附录第7节窄审查

**结论：7.1、7.2、7.3在修订后的明确前提下均与锁定D1一致，三项澄清已解决，无待修问题。** 源码保持423行及SHA256 `2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a`。本次只审新增第7节；未重审历史1–6节、五份最终文档、CSV或回归测试。完整SHA和定义域见 [theory_appendix_review.json](theory_appendix_review.json)。

## 7.1 固定快照单车资源下降

现已明确取实际 `_decide` 触发的 `_fill` 调用。源367行的第三参数为 `2 if receiving else lanes`，第四参数为 `receiving and mode=="transform"`；已通过AST核对该唯一调用。因此future为真必有lanes=2，实际候选和目的道都在0/1。

候选要求abs(vy)<0.1，故它不进入205–209行的运动投影分支，原资源就是实际lane；future的π在0/1上为恒等映射。一次固定集合重分配恰好使源计数−1、目标+1，`ΔΦ=2(Nt−Ns+1)`成立。254行排除非负值；成本排序不会改变该资格，原priority仍可否决提案。该命题只针对本帧单车假想转移，不推出多车同时动作或窗口切换后的全局单调。

定义域反例予以保留：仅有lane1 x700与x670两辆、均28.8m/s，若直接调用生产路径从不使用的 `_fill(...,lanes=3,future=True)`，返回lane2。π下1→2仍属于同一资源，(0,2)不变；因此不能把命题扩大为任意helper参数。相同输入经实际 `decide(transform)` 返回lane0的fill_layer，对应(0,2)→(1,1)，Φ由4降为2。这只解释定理域，不要求改API行为或源码。

## 7.2 新发出fill_layer的同gap绑定

现已明确限定 `_decide` 新发出reason=fill_layer且通过原priority的指令，未等同SUMO接受或完成。候选为ego时，`observed`排自身后恰为同帧rows；370行创建的新Memory使gap初值为None，371行调用未改的 `_join_speed`。191–193行再次以相同ego/rows/lane/空held调用确定性的 `_merge_target`，所以评分target与gap分别等于Command.target_x和Memory.gap。421–423行最终只裁剪速度，不改这两个字段。跨帧更新和真实横移成功不属于命题。

## 7.3 输入信息边界

现已把x窗口、实际lane与y/vy资源推断、speed公开响应评分分开，并显式固定mode和控制参数。源287行过滤局部观测，_fill使用该集合的子窗、同帧gap和公开CF预测；邻车pending/Memory/编队私有状态不进入这些计算，track只关联对象。相同局部输入、道路、自身记忆、模式及参数决定相同输出；该实现非干扰性质不等于带遮挡、误检或延迟的感知鲁棒性保证。

版本导航与新复算输出路径已标明历史/现行范围，本次没有运行历史theory_check或覆盖其结果。没有新增混合弦稳定、全局编队收敛、一般碰撞不变性或执行成功结论，也没有仿真、Git和源码改动。
