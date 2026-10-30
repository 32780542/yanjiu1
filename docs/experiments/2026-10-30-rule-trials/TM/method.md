# TM：在固定时距上加入补位制动代价

此候选以T为父版本，加入M的候选排序及目标道后车独立制动上限。公开反事实跟驰模型直接复用T的`_front_following`及原`safe_speed`，不另保留固定30米预测器；这样成本估计与当前基础跟驰相符，并减少重复代码。

NOA与T逐项同规则，试验继续引用T的NOA。M的代价判定只作用于自由补位，必要合流不受影响。先在T上记录3个预期断言失败，再实施；7项T合同及4项组合合同共11项通过。RED/GREEN为`results/operations/20261030T005414307880Z_literature-TM-incremental-red_2931e6f9`和`20261030T005434682420Z_literature-TM-incremental-green_d2fe9080`。

补丁相对于T，不相对于原base。实际车流结果单独列出；M在base上的改善并不能保证TM相对T仍有改善。
