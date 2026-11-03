# 紧凑案例证据

这里保存既有逐案例封包的原样归档。每个分组包含独立case_record和完整evidence目录：原始结果与逐车记录、自身0/1序列、冻结运行源码、需求、1000米断面括号和800–1000米区域积分。归档不包含全路positions/events大轨迹；完整轨迹的保留和清理另列实际执行记录。

`development600_short/index.json`列出C8持续开发54例与最终C12/P12短筛24例，共78例、21个分组。归档前调用既有离线验证器，归档后逐成员与原件比较，实际通过；共38,454,194字节。该包已在GitHub提交`f65333bfd94efbbe3957509e29baf56d7a77962f`，远端分支与本地指针核对相同。

随后只清理其中seed202的30个成功NOA/transform案例的60个positions/events原始大文件，释放267,173,719字节。逐件先核对已发布Git归档，再调用原有路径与SHA检查的定点删除；全部seed201轨迹和seed202的formation模式轨迹保留，其余批次、错误与未完成原件未动。实际记录在[cleanup_development202.json](../cleanup_development202.json)。完整0/1、逐车时间和区域证据继续在归档中。

分组保留原来的`cases/案例名/evidence/`相对结构。用tar解压到临时目录后，执行仓库原有工具：

```powershell
python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/seal_case.py verify 解压目录/cases/案例名/evidence
```

不加`--check-originals`时可独立验证紧凑数据；完整源码方法版本与原记录保持一致。表格里的复用案例只引用同一个原件，不把复用行计为新实验。
