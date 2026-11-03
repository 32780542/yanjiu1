# D1：真实gap选择与同gap执行

D1保留[D0完整方法](../real_gap_balance/method.md)，只将评分调用的邻车集合改为`observed`中排除候选自身的车辆。这是一行实际gap API修复，无空间尺度、增益、阈值、记忆或交通参数变化。冻结源码423行，SHA256 `2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a`。

## 同帧接口绑定

设本车e是当前局部winner，通过必要合流优先级复核并实际发起fill_layer，目标实际道为l。评分时输入为`observed=(e,*rows)`去掉e，因此恰好是本车实际`rows`；原`_merge_target(e,rows,l)`给出`(xgap,vgap,gapIDs)`。随后原自由补位分支创建空gap记忆，再调用未改的`_join_speed(e,rows,memory,l)`。它以同帧同rows、held=None调用相同`_merge_target`。故本次输出严格满足`Command.target_x=xgap`、`Memory.gap=gapIDs`，不依赖ego居中假设，也不增加目标记忆。

该命题针对本帧新发起的自由补位；不意味着预测的邻车响应等于其实际私有控制，不保证下一帧gap不变、其他车不选同gap、横移必完成，或SUMO最终速度等于名义请求。实际执行仍受原安全帽和执行器约束。原必要合流及已有动作继续沿用S，不作新的接入保证。

## D0差异核查

纯静态、固定随机种子的10000个局部状态中，5000个居中静止样本D0/D1命令和Memory逐位相同。5000个横向边界样本中4932相同、68不同；全部68个变化帧都实际记录到D0把偏心候选作为自身目标道gap成员。边界中共1068帧出现这种API污染，多数未影响最终输出。2448个NOA样本输出差异为0。

这些是局部状态样本，不是交通轨迹或无碰撞证据；不能称全状态相同。改变可能来自ego或其他参与评分候选的自身污染，不能把差异范围错误限制为“ego自身偏心”一种情况。完整计数和8组差异见[D0_D1_10000_comparison.json](D0_D1_10000_comparison.json)。

静态范围核验另含1000状态×2地图NOA与冻结S hexexact，safe_speed/public cf_speed各1000比较，以及全部核心函数和原response_cost/cf_cached的AST一致。交通收益仍须独立runner验证。
