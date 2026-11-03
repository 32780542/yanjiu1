# 交错编队与3→2瓶颈：2026-11-03迭代

本轮按用户授权持续迭代至北京时间17:00；达到独立验证的良好版本时提前交付。原目录为 `D:/yanjiu1/keyan1`，Git起点177f7a3，研究分支 `research/20261103-staggered-bottleneck`。本页当前为进行中记录，不是最终采用报告。

## 已确认的问题

[旧结果重新诊断](diagnosis/diagnosis.md)表明，500–1250每道基本接近巡航，1500平均仍接近自由流但有少量长停滞。NOA1500均值42.471秒，巡航参考41.667秒；五种子25/3660辆超过60秒。大幅改善平均时间需要检验真正有瓶颈积聚的需求，不能削弱NOA来扩大差值。

每道1750/2000/2250/2500、两种子、两道路及两模式的32例180秒负荷试验全部安全排空。2500时原TM比NOA明显更堵，两个种子行程时间增加40.974和37.389秒。逐步轨迹已定位旧提前开隙/等待链，正在独立保留事件证据。[局部方法与Cai源码核查](methods/reference_design.md)说明可借机制及实际信息条件。

## 独立尝试

| 项目 | 单一改变 | 当前处理 |
| --- | --- | --- |
| [A](candidates/gap_projection/method.md) | 已可横移时追安全区间的最近点而非中点 | 20例完成，明显负效益，不进入长批 |
| [C](candidates/effective_handoff/method.md) | helper必须当前能腾位且腾位确实解除阻挡 | 10例完成，结果混合，2500仍有明显负效益 |
| [D](candidates/continuous_phase/method.md) | 存续车道保持原交错相位 | 10例完成，小幅/混合，未解决高流量拥堵 |
| [NF/NC/NP/NH](ablations/README.md) | 分别关闭自由补位、提前协作、队首相位、helper | 用于定位环节；包括未排空结果 |
| [E](candidates/direct_gap/method.md) | 删除提前等待链，继续用真实F/R间隙变换 | 444行，等价NC；600秒需求筛查中 |

候选源码从固定Git重建到本轮临时目录；各目录保存补丁、源SHA与合同测试记录。A/C/D独立[源码与影子审查](review_candidates.md)及[机器结果](review_candidates_verification.json)覆盖NOA不变、局部信息、跟踪号重标和远车不影响。主入口此时仍为原TM，不以候选替换未经正式验证的默认程序。

## 试验与存储

[设计](../../superpowers/specs/2026-11-03-staggered-bottleneck-design.md)、[实施计划](../../superpowers/plans/2026-11-03-staggered-bottleneck.md)、[600秒筛查协议](long_screen_protocol.md)登记输入、对照和选择步骤。短批用于诊断与选择，正式[100,600)区域指标在不足完整时窗时保持空值；不能把短批曝光称作容量。

[工具说明](tools/README.md)提供冻结、逐例归档、离线复算和配对表命令。每例先核验原件与紧凑证据，再仅删除本轮生成的positions/events两个大文件；旧成果保持原样。紧凑字段保留原trips、全帧0/1、实际越线括号及既有区域账本，不能还原完整轨迹或任意新指标。代码分单元推送用户GitHub，最终证据与结果表在完成后追加到此目录。
