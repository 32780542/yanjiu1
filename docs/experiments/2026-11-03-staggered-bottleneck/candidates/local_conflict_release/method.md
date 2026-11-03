# N：本车解除终止道真实走廊的唯一占用

固定父L `e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a`，不叠M。沿用原自身moving/pending/Memory优先级，只有organized且非joining时，准备区lane1本车左道已_clear，才检查当前50m内、本身也已进入准备区的实际lane2车。它当前中道不_clear，且仅从本车同一局部观测移去ego后变_clear，本车才自主提交1→0，以原_join_speed跟踪真实左道gap。

这是一个局部物理因果反事实：ego恰好是当前唯一阻挡者。无需远处helper选举、群计数压力、成员标记或neighbor flags；不要求别人开隙，不提前从任何实际安全输入删除ego。多个阻挡者都不满足唯一条件时不协商，这个限制保留。失败仍继续原_fill，不能重复F暂停补位的损失。

规则自然且可小实现；它不能保证任何密度下都能释放，也不保证减少总换道。先专项红绿及原L合同审计，父独立筛查后判断。

## 局部判据及执行

在原_decide已有横移/Memory任务及必要merge分支之后、原自由_fill之前，仅organized且非joining、本车not moving、preparing且lane1时：

```text
本车_clear(left0)
存在当前实车 c：c.lane==2，c.x>=drop_x−360，abs(c.x−ego.x)<=50
  _clear(c, 当前(ego,*rows), middle1) == False
  _clear(c, 同一rows只移去ego, middle1) == True
=> 本车Memory(lane_target=0,joining=True)
   使用原_join_speed追踪本车当前左道实际gap，提交release_ending
否则继续原_fill及其后分支
```

not moving复用原本车测量布尔量，避免“已有实测横移但Memory暂为空”时新发反向提案；没有新阈值。lane2车的原preparing条件简化为c.x>=drop−360（原条件中lane2允许一直到实际退出），并非提前读取其private阶段。

反事实只用于判断**本车**是否释放，不改变任何实际安全输入。终止车仍看到ego当前物理占用；直到ego真正离开中道后，它才可能以原_clear并入，没有虚构helper已完成或等待标记。可释放多个incoming时动作都只有本车→0，不选择incoming ID或给它排序。

在原speed≤33.3、1s_clear预测下，能使ending走廊不_clear的车相距至多33.3+8=41.3m；ending与ego≤50m，因此这些相关阻挡者均在ego±91.3m内，覆盖于现有观测[−100,+200]。此判断不需要远处车辆或ending私有观测。多个中道阻挡者移去任一后仍不_clear时，规则不会选人协调；这不是缺失一个待补的全局调度器，而是本候选保留的局部能力边界。

## 源与合同

新源 `tmp/staggered_bottleneck/candidates/local_conflict_release/native_rules.py`，SHA `5d21af5456e816c927116a66895db29d03fada7b28057ecef266b60a0d92a0d6`，467行/有效+8，仅_decide一条新提案。父L的跟驰、相位、gap、安全、车型/道路参数均原样，未叠M或NoA60。见[build](build.py)、[patch](native_rules.patch)及[source.json](source.json)。

[十五专项](../../tests/test_local_conflict_release.py)检查左受阻/ending本来clear/去ego仍阻/ending自身未prepare/远处和其他ego车道不发release；正例跟踪真实左gap；自身已有执行、joining、无Memory实测横移都不被新角色覆盖；保留原fill；终止车等实际占用解除才并入；多incoming重标/重排/远车无ID分配；600已存局部state的完整NoA Command/Memory、cf_speed、safe_speed精确相同。

- L上最初14项：`20261103T062340752188Z_N-local-unique-blocker-release-red_4855560e`，exit1，4预期失败、10通过/4子测试通过。随后在实现前补上无Memory但实测moving的保护合同。
- 构建：`20261103T062515265153Z_N-local-unique-blocker-release-build_d747446a`，exit0，反向精确恢复L，AST仅_decide。
- N专项：`20261103T062633179994Z_N-local-unique-blocker-release-green_30da860f`，exit0，15项/4子测试通过。
- 原L30不改审计：`20261103T062633182176Z_N-inherited-L30-unmodified-contract-audit_9b497dda`，exit0，30项/106子测试通过。

未跑仿真、未改原候选/生产/tests、无Git提交。父可独立筛查N，再决定是否做225项及正式比较；N不叠到已有M正式批。
