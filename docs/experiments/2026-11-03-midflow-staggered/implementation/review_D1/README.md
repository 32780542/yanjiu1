# D1 独立代码与方法初审

冻结候选：`tmp/staggered_bottleneck/candidates/midflow_real_gap_balance_v1/native_rules.py`，423 行，SHA256 `2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a`。比较源固定为 S 候选 SHA `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`，不把正在安装的生产文件当作 S。

**结论：未发现可复现的 critical、important 或必须修复的 minor 实现缺陷。** D1 是内在一致的局部纯规则方法；同帧新发起 `fill_layer` 的评分 gap 与原加入执行绑定成立。局部假想势能下降不能被写成全局单调、所有 winner 必执行或交通收益证明。最终 91 批的运行结果不属于本审查，不能据本单元声称已通过。

## 最小优先级反例及命题范围

四车全部 28.8m/s：lane0 车头位置 x700、x670、x640；lane2 一车 x700。它们在同一局部集合内，future 计数为 `(3,1)`。每辆 lane0 假想转到 lane1 都满足 ΔΦ=−2，前两辆都通过原 8m `_clear`。源 261–267 行选 x700→1 为 winner，但 369 行保留的 `_mandatory_priority` 因同 x700 的必要合流车而否决它，实际输出 `lane=None`、`memory.gap=None`。x670 自身不会被该 priority 否决，却因当前 winner 是 x700 而同样不动作，没有自动晋升第二选择。

这不是安全错误，也不要求增加新重试机制。它是“假想可行机会 → 原优先级 → 本车请求 → 执行器”的既有分层边界。D1 method 后文已经限定“本帧新发起的自由补位”，按实际 `fill_layer` 理解时其绑定命题没有被反例推翻；前句若简称“winner 即推出绑定”，应补足“通过原 priority 并实际发起 fill_layer”的前提。反例和全部输出保存于[结果 JSON](review_d1.json)。

## 信息、计数与数学核对

- 源 287 行仍只取前 200/后 100 米观测。203 行的原可见组件与 ±90m 窗口只访问这些观测；响应评分使用同一已可见 `observed`，没有为其他候选补读其私有视野。
- 205–212 行只用实测 lane、y、vy 估计运动到达资源；没有读取邻车 pending、意图、joining 或私有 Memory。每车至多累计一次。ceil/floor 是可见运动投影，不能当成读到了对方真实目标；正好在车道中心、测量抖动或接近 vy 阈值时，它也可能暂时仍计当前资源。
- future 映射只在 transform 接收时将实际 1/2 道归到同一存续资源。候选为未测得横移的实际允许道车辆，因此候选自身按其实际 source 资源计数。固定集合的一次假想转移严格满足 `ΔΦ=2(Nb−Na+1)`；254 行只留负值。它不涵盖视窗变化、同时局部选择、原 priority 否决、持续横移、必要合流或实际安全执行，所以没有全局单调结论。
- 256–257 行使用真实 `_merge_target`，候选自身已从评分邻车中排除，目标差不超过原 GAP，并保留原 `_clear`。237 行原新后车制动上限与整个 response_cost/cf_cached AST 均保持 S，不用其他车辆释放收益抵销新后车损失。该公开模型评分不等于邻车私有实际响应，也不构成独占 gap 预订。
- score 全是公开成本与几何量，track 只作身份关联、排除自身和 winner 与 ego 相等判断，不进入排序。只输出当前 ego 的动作，不替其他车写目标。

## 执行与范围

D1 与冻结 S 的类、模块常量和所有函数 AST 相同，例外仅 `_fill` 与 `_decide`；math import 增加 ceil/floor。原 CTH、纵向相位、真实 gap 跟踪、Memory 三字段、硬安全和执行流程未改。原 response_cost/cf_cached 两个嵌套函数 AST 也完全相同。

receiving 可以由本车 preparing 或 ±90m 实测 ending 已进入公开准备段触发；它使存续道提前平衡、取消尚未启动的新入 lane2 请求。已有 moving 或本车 pending 沿原分支继续。必要合流的 `preparing and ego.lane==2` 分支仍在原入口；这不禁止准备段外原本可发生的自由补位。NoA 输出保持 S；formation 与直路的组织动作有意使用新真实 gap/局部负荷策略，不能要求等于旧 grid 行为。

当实际新发起 `fill_layer` 时，评分传入 `observed` 去掉 ego，恰为本帧 rows；之后以空 held 调用未改的 `_join_speed` 和同一 `_merge_target`，所以评分 target/gap 与 Command.target_x/Memory.gap 相同。跨帧持有、其他车辆选择同 gap、横移完成及实际速度都不在此命题内。

## 独立验证

[核验脚本](review_d1.py)不使用 Git。它在内存中只将原测试的 `git show` 读取替换成已核 SHA 完全相同的冻结 S 文件读取，原测试文本和断言没有改动或跳过。原 10 主合同与偏心自身排除合同共 **11 项全部通过**，其中包含 1000 状态×两地图 NoA hex 精确比较、各 1000 次 safe_speed/public CF 比较、core 与 response cost AST 检查。

额外 700 组随机接口压力输入验证标签重标、观测重排、邻车 pending/acceleration/time 扰动及感知外车辆不干扰；其中 25 个实际新发起 fill_layer 输出的评分与执行 gap 全相同。该压力输入含 lane/y 不一致的合成边界，**不是 700 个有效物理状态或交通轨迹**；它只验证接口不变性与绑定，不作为几何或安全效果证据。上面的四车 priority 反例另使用居中、无横移的实际几何输入。

operation `20261103T135355050174Z_D1-independent-core-scope-identity-binding-and-priority-review_9d51a985`，exit 0、0.906 秒；11 项 unittest 为 0.168 秒。脚本 SHA256 `8dff9354d26dbabc94728ed0bf1d4759527cff967285c45b0f26e19bb52cc151`。候选 D1、冻结 S 和原两份测试运行前后逐字不变；不对父任务正在替换的生产文件做不可变断言。没有交通仿真、Git 或修改旧证据。

## 完整方法判断

“实测运动投影后的局部资源负荷 → 仅允许假想平方和下降 → 真实相邻 gap/原 clearance 与 CF 代价 → 本地 winner → 原优先级和执行”构成统一规则。它删除旧 grid/full 保护，而不是把多个弃用候选的纵向机制继续拼接；没有新增增益、等待状态、接入门禁或 ID 特判。保留原安全优先级造成的 veto 和局部信息造成的不一致选择是可解释的限制，不能由此反推需要中心调度或隐含通信补救。
