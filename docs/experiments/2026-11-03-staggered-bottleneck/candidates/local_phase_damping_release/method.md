# MN：仅合并已独立验证的M反馈与N本车释放

固定父M `a286110cf2e14904152b63c9a66f960496f5f7f04ab0097b8d7ed00353db4762`、N `5d21af5456e816c927116a66895db29d03fada7b28057ecef266b60a0d92a0d6`，共同父L `e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a`。只合M实际互选边相对速度反馈与N八行唯一阻挡释放，不增加条件/层级，不叠NoA60。

构建要求：先核M=L+一式、N=L+八行；M再加N与N再加M逐字节一致，并能分别逆变回两父源。相对L的AST仅_following/_decide两函数变，Memory类AST完全相同。原M9/N15合同不修改，另运行原16相位/物理邻接合同审查；历史J2专有精确等价冲突必须单独报告。

本子单元不跑交通、生产/Git不动。root统一screen与后续确认；静态通过不等于两方法交通收益可直接相加。

## 冻结源与合并证明

新 `tmp/staggered_bottleneck/candidates/local_phase_damping_release/native_rules.py`，SHA `de14e066ac74f84d21cbd0d06fcf4abde1cfcc5f033ceea26d2824905935d18e`，467行。[build.py](build.py)硬断言两条路径字节一致，并验证L→M、L→N的完整父差异恰是预期一式/八行。

[native_rules.patch](native_rules.patch)保存L→MN，[M_to_MN.patch](M_to_MN.patch)只加N，[N_to_MN.patch](N_to_MN.patch)只加M；每路能精确逆回各自父源。[source.json](source.json)保存各源hash、两函数AST范围及Memory类AST hash `55abc9515078b93eba8f2a022e26d08d3004fd6449aaf9873d0a54d188543fdb`。Memory结构/字段完全不变，释放动作写入的仍是N原有lane_target/gap/joining。

## 原合同审查，不改历史期望

先把联合M9/N15分别放在单M、单N父源，确认每个单项都缺另一条行为：M父有4项释放合同失败；N父有3主项/5子断言反馈合同失败。MN原样运行后 **24项/24子测试全过**，覆盖相对速度符号与反对称、同速平衡、真实front CTH目标/ref、硬安全、原clip、释放失败继续fill、正在横移/自身Memory优先、incoming等真实占用消失、重标/远车，以及各自600个完整NoA/CF/safe精确比较。

原16相位/物理邻接审计为 **15通过、1历史政策冲突、101子测试通过**。唯一失败仍是 `test_without_actual_lane_two_both_policies_are_exactly_their_frozen_parent`：该测试属于J2一行物理邻接修正，要求无lane2时所有异速控制等价旧J0。M的PD有意改变异速速度，MN同样不满足；首例速度6.941506对6.274102，而target1017.751113、reference7与Memory相同。该历史测试保持原文/原hash，不跳过、不换新数值。其余原50m相位边界、并列body修正、30/15平衡、实际front/硬安全、NoA与relabel合同均通过。

本单元没有扩大M225补丁或运行新交通。组合会在闭环中相互影响，必须由父统一MN短筛再决定正式矩阵。

## 操作

- 联合合同放单M：`20261103T063653787551Z_MN-contracts-on-M-parent-red_67f67030`，exit1，4失败/20通过/24子通过。
- 联合合同放单N：`20261103T063653802422Z_MN-contracts-on-N-parent-red_335e7d16`，exit1，3主项+5子断言失败。
- 双路径构建：`20261103T063746718827Z_MN-independent-two-path-composition-build_9566274f`，exit0。
- MN联合绿：`20261103T063800433683Z_MN-M9-N15-contracts-green_6263db7c`，exit0，24/24。
- 原16不改审计：`20261103T063800437553Z_MN-original-phase16-unmodified-audit_16179fb7`，exit1，15/1/101，以上政策冲突留存。
