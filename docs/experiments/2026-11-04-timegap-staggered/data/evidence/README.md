# 紧凑案例证据

这里保存既有逐案例封包的原样归档。每个分组包含独立case_record和完整evidence目录：原始结果与逐车记录、自身0/1序列、冻结运行源码、需求、1000米断面括号和800–1000米区域积分。归档不包含全路positions/events大轨迹；完整轨迹的保留和清理另列实际执行记录。

各组归档前调用既有离线验证器，归档后逐成员与原件比较。按实际新案例计数，复用参考行不计第二次：

| 目录 | 实际案例 | 分组归档数 | 归档字节 | 内容 |
| --- | ---: | ---: | ---: | --- |
| [development600_short](development600_short/index.json) | 78 | 21 | 38,454,194 | C8持续54例、C12/P12短筛24例 |
| [formal_main_and_long](formal_main_and_long/index.json) | 159 | 21 | 124,049,409 | 正式主135例、长时24例 |
| [formal_parallel](formal_parallel/index.json) | 45 | 9 | 27,939,623 | 五种子匹配并排新增45例 |
| [posthoc_front_and_cap](posthoc_front_and_cap/index.json) | 81 | 18 | 48,839,564 | 扩展NOA45例、共同28.8上限36例 |

开发78例已发布在`f65333bfd94efbbe3957509e29baf56d7a77962f`，正式主及长时159例已发布在`a30605e9e13736e1a09358e2716528d5731ba9b6`。后续分组随本轮最终提交发布，提交位置以[GitHub分支历史](https://github.com/32780542/yanjiu1/commits/research/20261104-timegap-staggered/)为准。

随后只清理其中seed202的30个成功NOA/transform案例的60个positions/events原始大文件，释放267,173,719字节。逐件先核对已发布Git归档，再调用原有路径与SHA检查的定点删除；全部seed201轨迹和seed202的formation模式轨迹保留，其余批次、错误与未完成原件未动。实际记录在[cleanup_development202.json](../cleanup_development202.json)。完整0/1、逐车时间和区域证据继续在归档中。

第二次清理只处理已发布的正式主与长时四批数据。先比对Git提交中的归档、归档中各成员与本地紧凑证据，再由原删除工具逐件核对绝对路径与原SHA。77个成功案例的154个positions/events文件实际释放1,383,088,873字节；[cleanup_final_plan.json](../cleanup_final_plan.json)中逐例列出取舍与最终execution。正式seed211全组、长时seed201全组、关键反例及最差形成样本等82例的164个大轨迹仍在。独立验收逐件确认已删与保留文件符合清单。

两次合计实际释放 **1,650,262,592字节**，约1.65 GB。这是删除大文件的总量，不扣除本轮新增实验和归档。其余成功反例即使清理全路大轨迹，逐车结果、0/1和区域证据仍按原值保留；失败、未完成及其他批次不在上述删除范围内。四组车群几何另有[完整逐步轨迹包](../cohort_trials/README.md)，用于观察形成、运动引导和恢复过程。

分组保留原来的`cases/案例名/evidence/`相对结构。用tar解压到临时目录后，执行仓库原有工具：

```powershell
python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/seal_case.py verify 解压目录/cases/案例名/evidence
```

不加`--check-originals`时可独立验证紧凑数据；完整源码方法版本与原记录保持一致。表格里的复用案例只引用同一个原件，不把复用行计为新实验。

紧凑包可复算已定义的交通、0/1与瓶颈区域指标；它不包含被清理的全路positions/events，不能从包中恢复任意新空间窗口的原始轨迹。全路时空图与相位分析使用明确保留的seed211，来源在各图说明中列明。
