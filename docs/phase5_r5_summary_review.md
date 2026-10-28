# R5外层机制与运动摘要独立审查

**结论：所列版本通过独立审查，无未关闭 P1/P2。** 可在正式R5源包完成封存后使用此工具输出描述性摘要，并用输出中的脚本/依赖快照重放。它不运行控制器、物理模型或SUMO，不代替[标准R5记录重放](/D:/yanjiu1/keyan1/docs/phase5_r5_records_review.md)，不产生方法选择分数或科学通过结论。

| 文件（root相对路径） | SHA256 |
|---|---|
| tmp/phase5_r5_summary.py | 09efc4ddafc8573dc7b0c053e164a0891b1d9c3494da6701a8c6958f7f097658 |
| tmp/test_phase5_r5_summary.py | aabb0692db981936f0915295cfc883921e398521490d38c498f1bc5d99301f76 |
| tmp/phase5_motion_summary.py（冻结依赖） | 1cbdab1433ec01f7547f58dfa873eab0355588249ad0df23a1f6d10576d8b6ca |

本次未修改上述源码、任何控制/配置或正式run，没有读取heldout性能。独立探针、源码快照与结果在 `tmp/phase5_r5_summary_review_20260913/evidence_v1/`，前后文件hash一致。

## 已核实的计数与范围

- 从冻结case、明确sampling开关重建完整变体声明，检查started/finalized为执行顺序前缀，completed与逐case metadata一致。未启动变体仍占声明矩阵的位置，mechanism/motion为null；它们不是零次退避、碰撞或成功。无trace失败、物理失败前缀和完整执行分别表示。
- 私有输入须接上上一成功提交的memory。请求draw/plan从保存decision统计，已提交draw/state/plan及阶段时长只在`status=completed`推进；失败决策可作为观测保留，不能增加已提交时长或完成机动数。phase时长为成功控制区间的左端decision phase乘dt，不是从浮点deadline插值出来的连续等待时长。
- 逐actor重构的事件表、请求/提交总数须与保存的`r5_events.json`和case/top validation相符。`first_eligible_s`和速度门槛统计是观察到的决策事实，可以包含未提交失败决策；事件本身带`committed`标记。ELIGIBLE、阻塞解除、guard接受、新plan提交与机动完成是不同事实，未被合并为通行成功。
- OFF/ON必须共享case、物理和私有初态、模型及除R5开关外的参数，formation两侧保持开启。只有完整共同窗口才输出描述性计数差；失败或未启动配对为null。半控制采样只允许控制/感知周期均减半，其余策略/数值参数保持相等。
- 同私有初态和两个记录deadline落入同一最早行为网格仅为离线描述。该网格只将deadline按原行为采样容差取整；不能证明准备完成、双方同时真正启动、互斥、赢家或一定通行。没有根据这些数值反过来分配随机流、选择方法或控制释放。

## 运动与来源边界

工具按固定SHA载入已审motion helper，只调用其`.01s`主轨迹汇总。初态/末帧各一次、相邻控制记录连续、末帧等于最后子步、子步/diagnostic数量和时间均检查。速度积分使用原梯形口径；停车时间沿用source phase2登记的`1e-6m/s`左阶梯口径。实际加速度/jerk来自既有初态观测公式和保存diagnostics，完整受控车标准metrics仍须存在并交叉核对，外生车不被冒充已有标准受控车metrics。

此工具**没有**调用`.005s refinement_summary`，也未产生raw局部并集、最大组覆盖或选择指标C。需要这些量时，应另用相应已审工具和明确数据来源；不能将本输出写成已完成`.005s` jerk验证。

来源检查覆盖全证据文件集合/hash及code/input快照内部集合/hash，拒绝路径逃逸和新增未登记文件。冻结case文件字节hash与metadata相符，逐case/开关初态相互绑定；分析结束再次校验源包。输出要求新目录、位于源包外，并封存自身脚本和固定motion依赖；输出目录重复使用会拒绝。

这是一份**来源与会计关系验证**，不是源controller/生成器/physics/SUMO语义重放。`source_validation_without_variants`和`source_paired_actions`是明确标注的原包声明，后者没有被此工具重新计算；不能只凭`analysis_passed=True`认证它们的算法/安全真实性。正式验收需同时绑定独立标准R5 replay及其源包hash。`formal_seventeen_variant_shape`只表示8case/17变体的结构，不证明时长、生成器或该包是正式实验。

## 独立实验与负探针

日志：`results/operations/20260912T221225439029Z_phase5_r5_summary_independent_941d97e5`，登记Python经`run_logged`执行，退出0、4.078s。结构化结果为 `tmp/phase5_r5_summary_review_20260913/evidence_v1/result.json`。

1. 独立复跑作者最终17项synthetic测试全部通过，覆盖无trace、失败尾、丢actor决策、请求/提交、参数、来源集合、配对和快照重放。
2. 新增一个**失败前已算完整物理区间、但尚未commit**的合成尾部：物理观察窗口为0.4s，阶段成功提交时长只有0.3s；请求2次draw和1个新plan，实际累计提交只有1次draw、0个新plan；motion的full_window为null。没有将可用积分结果补成成功执行。
3. 配对策略参数仅改`1e-12`仍拒绝；半采样增加未登记参数拒绝。改变最后final而不改最后保存sample，被motion拒绝。合成封存包增加内部未登记源码文件、随后重封外层hash，仍因内部集合不等而拒绝。
4. 只读真实生产格式的**0.2s单元包** `variants/phase5_r5_common_development/tmp/r5_failed_package_test_gcsk5wyy/runs/20260912T215614684669Z_7ed49d2d`，并未运行车辆。其evidence manifest SHA为`4017059173a3a927dee05c91be4f0ec41c0ff6b66a91aeeeea6afb7361494ef8`。独立摘要保留3完整、1失败、13未启动；竞争on记录2次请求draw而0次提交，配对完整窗口差为null。
5. 从新摘要目录保存的`script_snapshot.py`在`D:/yanjiu1`异cwd重放，summary、script、motion、analysis_validation及manifest整个文件映射字节一致。源包前后集合/hash均不变。它只证明对该短失败夹具的重放，不是正式20–40s机制效果。

## 容易误读的字段与下一入口

`plans_started_after_observed_wait`是该actor在**历史上曾成功提交blocking之后**出现的新plan集合，跨episode clear或不同后续episode也可计入；它没有证明同episode退避引发启动。`actual_lateral_displacement_m`沿用canonical事件字段：在失败但已有某车step时，它仅是该可用积分step的位移，`committed=False`，不能据此称控制已提交或车辆已通行。guard的`committed_rejections`表示所在决策区间成功提交且该请求曾被拒绝，不是把被拒绝请求施加到车辆。这些解释没有改变指标或控制机制；作者已在[工具单元说明](/D:/yanjiu1/keyan1/docs/phase5_r5_summary_unit.md)补充主要范围。

下一入口为正式新R5包完成后先核对源绑定/标准重放，再运行此独立摘要和快照重放，保留真实未触发、未启动、守卫拒绝、低于5m/s门槛、对称/同网格及物理失败事实。无改善或失败照实输出，不改变冻结种子、阈值或旧A/B/heldout结论，也不因此开放阶段6。
