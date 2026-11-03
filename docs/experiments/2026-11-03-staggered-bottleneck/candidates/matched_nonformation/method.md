# G0 / G0N：匹配gap执行的非形成对照

父分别为固定M/N。移除全部形成following（含相位速度、L witness桥接及head形成响应）和交错几何补位；保留原CTH、真实gap必要并入/自身执行/硬安全，G0N保留独立N释放。_fill改用原NoA慢前车自主超车择空逻辑，避免把NF移除所有自主换道的损失统称交错收益。

这两版必须标为 **matched-nonformation control**，以mode transform运行是为保持与原被消融者相同gap/Memory执行流程，不是原纯NoA。原NoA block保持逐字不动；NoA模式的完整输出必须与各父精确相同，所有本候选关系flags报0。

最小构造仅替换_following/_fill。mandatory_priority仍由原_decide post-guard处理：原规则只可能阻止lane0→1，这时只有一个邻道候选，因此与NoA候选前过滤等价；其他ego车道该priority恒False。准备区caller给_fill传lanes2，故不进closing，无须新drop参数或调节阈值。

G0N−G0必须以源码证明只差N八行release；M−G0、N−G0N识别的是额外形成策略包（含相位反馈、witness/head处理、几何补位），不是其中某个单独几何项的纯因果。不同控制之间的闭环交互仍须真实同输入验证。

## 冻结身份与匹配范围

| 对照 | 固定父 | 新源SHA256 | 行数 |
| --- | --- | --- | ---: |
| G0，matched_nonformation | M a286110c…b4762 | 1ca965ae0cbaa373f97c48757ca54ddaa907fc839d1a3ef62e962d5fa498b1a6 | 337 |
| G0N，matched_nonformation_release | N 5d21af54…2a0d6 | d4124d14568b282585395efd118a9ea434adcd1f73b40ae08159d97184b6302f | 345 |

源在 `tmp/staggered_bottleneck/candidates/` 各同名目录。[共同build](build.py)只替换每个父的_following/_fill；硬断言整个_decide函数文本逐字不变，故原NoA block、真实gap并入/接近、已有Memory/横移优先和N原release都未改。所有常数、_front_following默认50m、cf_speed、safe_speed、_clear和车型供给均不改。相位/几何旧helper定义保留以缩小审查范围，但新控制调用路径不再使用它们。

G0N与G0的AST只差_decide，且完整文本差异硬断言正好是原N八行，不只是声称两个父“差不多”。Memory结构不变；N礼让对照因此不混入M相对速度反馈差异。

## 新非形成决策

```text
following: 原_front_following返回的speed/target/reference，关系状态强制0
free proposal:
  本车及同道实际前车均低于CRUISE−2
  原邻道顺序、lanes边界与_clear筛选
  取原free_distance最大者，只有比当前前车远15m才提交
  由未改_decide的mandatory_priority和真实_join_speed/Memory执行
```

没有慢前车时不能按缺格几何换道，同速交错位置或邻道witness都不调距。自主超车能力保留，因此和NF“直接关闭_fill而无替代自主提案”不同。

省去_fill内部priority参数并非删除优先：原_mandatory_priority只在ego lane0/target1可能True，此时邻接候选只有lane1，原post-guard拒绝与NoA预过滤后无候选完全相同。ego1/2该priority恒False；准备区传入lanes2等价原NoA排除closing的显式条件，最大空隙/几何打平局顺序保持。

NoA模式不进入这两个被替换函数：原_decide的organized为False，following直接走原_front_following，_fill分支不执行。因此原NoA完整控制/Memory保持，且有600组每版实际精确比较。transform模式仍保留organized执行框架，含joining和真实gap跟踪，**这正是它不等于原纯NoA的原因**。去掉形成following后，闭环轨迹和join完成时机当然可能改变，不能声称任意轨迹上的Memory数值都与形成父相同。

原_decide日志标签仍沿用：`fill_layer`此处表示匹配的慢前车超车提案，`formation_follow`也可能出现，但所有formation_state=0。评价时必须按候选身份解释，不能把这些旧字符串当实际交错形成事件。

## 归因读法

| 同输入差值 | 能识别什么 | 不能声称什么 |
| --- | --- | --- |
| M−G0 | 相位PD、witness/head形成响应及几何补位的整体形成策略，相对保留自主超车的匹配控制 | 单凭这一差值把全部收益归给某一种交错几何项 |
| N−G0N | 保持同一N释放规则时，额外L形成策略包的作用 | 把N礼让收益再次算成形成收益 |
| G0N−G0 | 源码只增加N释放的纯局部礼让增量 | 与原纯NoA之间的无条件等价 |

全局真实几何评价仍可进行；状态0只表示本对照不声明形成关系，不禁止交通偶然出现交错。

## TDD和保留的真实执行

[十二合同](../../tests/test_matched_nonformation.py)在原M/N上出现23个失败主/子断言后，新两版 **12项/28子测试全过**。合同包括：无phase/相对速度或witness跟随、实际front CTH精确且flag0、原NoA慢前车择空/相等时低侧优先、closing与mandatory_priority、巡航缺格不补、真实安全merge/不安全approach、已有横移gap任务对父控制/Memory一致（仅flag0）、N释放/实际占用等待及非唯一阻挡不释放、远车/重标、600组每版完整NoA和1200个形成模式状态0/安全检查。

- 红：`20261103T065714415567Z_G0-G0N-matched-nonformation-red_8f490349`，exit1，失败符合形成移除及新超车提案预期。
- 构建：`20261103T065851077573Z_G0-G0N-matched-nonformation-build_e8176458`，exit0。
- 绿：`20261103T065931252301Z_G0-G0N-matched-nonformation-green_63e9c57e`，exit0，12项/28子测试通过。

原M/N/生产源及原tests保持。未跑仿真、未提交Git；root统一同输入对照，不能预先按本构造宣布交错优势成立。
