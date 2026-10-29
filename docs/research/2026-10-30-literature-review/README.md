# 150篇编队形成与变换文献

检索日期：2026-10-30。围绕现行纯规则、无通信、有限局部感知方法，完成153条初筛，去重后150篇。31篇读到相关正文章节，116篇读到摘要或公开预览，3篇仅题录。控制代码和现有实验保持原样。

建议先读[文献结论与方法建议](文献结论与方法建议.md)。主要方向是：固定时距与可选第二前车感知；自由补位的邻车制动代价；合流前后组织参考的连续恢复。队首滞回、相位死区作为后续可选项。现有0/1直接统计继续保留。

## 文献库怎么用

| 文件 | 用途 |
| --- | --- |
| [文献目录.md](文献目录.md) | 逐篇中文概要、方法联系、信息条件及阅读深度 |
| [papers.csv](papers.csv) | 用Excel等筛选题名、年份、DOI、适用性与定位；UTF-8带BOM |
| [papers.json](papers.json) | 完整主库、各组记录映射、读取范围、版本说明和核对证据 |
| [references.bib](references.bib) | 导入Zotero或其他文献管理器，条目键为L001–L150 |
| [检索方案.md](检索方案.md) | 检索范围、信息限制、去重和方法提取口径 |
| [catalog_audit.json](catalog_audit.json) | 数量、去重组、阅读深度和初筛文件摘要 |
| [verification.json](verification.json) | 题录、引用、目录、书目及源码未改动的离线核验 |
| [reproducibility.json](reproducibility.json) | 离线重建五份主目录文件的逐字节一致性与SHA256 |

153条来自A跟驰53条、B形成50条、C合流50条。重复的是IDM、增强IDM及Flow-Aware形成研究，分别合并。会议论文和研究性书章按实际类型保存；未找到可靠DOI的条目保留来源链接，未补造标识。

141条DOI经过独立核对：140条由Crossref API确认，中文图与势场论文由《自动化学报》官网确认。另核对了题名副标题差异，并订正了Scarinci/Heydecker综述的年份卷号。详见[catalog_corrections.json](catalog_corrections.json)、[crossref_checks.json](crossref_checks.json)和[限流重试记录](crossref_retry.json)。Crossref无记录不表示原期刊DOI无效。

## 建议优先读的来源

| 编号 | 文献 | 对当前研究的直接帮助 |
| --- | --- | --- |
| L021 | Donà等，2022，多预瞄无V2V ACC | 利用第二实际前车，不增加通信 |
| L009 | Gunter等，2021，商用ACC串稳定试验 | 跟驰扰动输入与实测验证方式 |
| L019 | Zhou等，2022，低层执行与串稳定 | 区分请求与实际运动，检查限幅后的结果 |
| L104 | Kesting等，2007，MOBIL | 考虑换道对新旧后车的制动代价 |
| L109 | Keane/Gao，2021，前车切换松弛 | 平顺恢复组织参考，减少交接扰动 |
| L099 | Woo/Skabardonis，2021，Flow-Aware | 形成更长队伍也需要考虑组织成本 |
| L054 | Cai等，2024，多道混合流形成 | 形成/执行分层，明确全组分配的边界 |
| L121 | Rupp等，2018，无通信车道减少合流 | 主题很接近；本轮只取得摘要，优先进一步获取正文 |

原文链接都在主库和目录中。`full_text`表示读到相关重点章节，不表示逐页逐式通读；摘要预览也不计作全文。Cai2024正文采用用户已有原PDF，线上核对题录。Rupp2018没有据摘要编造滑模公式。

## 分主题记录与核验

[A跟驰](A_acc/synthesis.md)、[B形成](B_formation/synthesis.md)、[C合流](C_merge/synthesis.md)保留各自分析。分组papers.json为初筛记录，最终引用以根目录主库及订正为准。全文临时缓存不加入Git，主库仅保存简要中文概括、来源和阅读定位。

离线重建目录及书目：

```powershell
python -X utf8 -B docs/research/2026-10-30-literature-review/build_catalog.py
python -X utf8 -B docs/research/2026-10-30-literature-review/verify_catalog.py
```

`build_catalog.py`只使用已保存的分组记录、Crossref元数据和订正，不请求网络。`check_crossref.py`与`retry_crossref.py`用于重新核对在线题录，重新查询会产生新的获取时间。
