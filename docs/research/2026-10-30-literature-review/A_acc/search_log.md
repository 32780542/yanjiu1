# 检索与阅读审计（主题A）

检索日：2026-10-30 Asia/Shanghai；本轮UTC时钟核对为2026-10-29 17:10:30 UTC。任务范围：无通信ACC/串稳定、固定间距/时距、有限多前车、时延/异质性、真实ACC波动。只写新建A_acc目录，未运行Git，未修改生产代码、测试或历史研究资料。

## 方法及读取深度

- 实际使用网页搜索/打开出版社、作者大学仓库、arXiv及作者稿；优先原论文摘要/公开正文。搜索聚合页用于发现和交叉核对，不作为技术结论的独立证据。
- 一轮Crossref标题查询尝试52个候选标题；多数受HTTP429限流。失败和错配保留在 `metadata_candidates.json`，**不计为已阅读论文**。部分标题本身是检索线索而非最终真实题名，未自动收入最终库。
- OpenAlex测试同样返回429，未用其生成技术摘要。最终53条由人工读到的材料编写，2条只标metadata；11条正文读到的实际位置写入`evidence_locator`。
- PMC通过网页工具有时触发验证码；本机requests取得正常全文HTML后提取文本。8个候选PDF在内存读取并提取文本，未保存PDF。Liang2000 PDF是扫描件，提取仅355字符，故其最终记录保持abstract，没有冒称全文阅读。
- 检索中出现商用ACC新闻、ResearchGate、博客、二手学生报告等，未用来替代原论文。Stern2018搜索返回一个同名学生综述，已排除，收的是原作者arXiv1705.01693/期刊版本。
- `papers.json`的abstract可能对应真实期刊摘要或所注明原文片段；不代表全文。全文材料也只对已读取章节作结论。

## 实际查询式（按主题整理，均在本轮执行）

1. `string stability adaptive cruise control autonomous vehicles Swaroop Hedrick 1996 string stability interconnected systems`
2. `string stability commercial adaptive cruise control Gunter Stern 2020 2021 experimental`
3. `vehicle platoons without communication time headway string stability multiple predecessor sensing review`
4. `adaptive cruise control string stability constant time headway Liang Peng 1999 2000`
5. `string stability heterogeneous platoon adaptive cruise control Kesting Treiber 2010 improved intelligent driver model`
6. `multi anticipative car following model string stability Lenz Wagner 1999 Treiber 2006`
7. `Makridis Mattas Ciuffo adaptive cruise control empirical study properties string stability openacc`
8. `commercial adaptive cruise control experimental string stability traffic oscillations Li Chen Zheng 2021`
9. `adaptive cruise control response time time headway empirical characterization road capacity 2018`
10. `multi anticipative car following Lenz Wagner 1999 anticipation model stability`
11. `Treiber Kesting Helbing 2006 Delays inaccuracies anticipation microscopic traffic models`
12. `multi anticipation adaptive cruise control radar two predecessor no communication string stable`
13. `"Multianticipation for string stable" Montanino Tufo authors 2022`（该猜测作者不正确；实际核实作者为Donà等，已纠正）
14. `"Stabilizing traffic flow via autonomous vehicles" heterogeneous time delays`
15. `"Car-following models: fifty years of linear stability analysis" abstract`
16. `"On the string stability of car following models with anticipation"`
17. `"heterogeneous string stability" vehicle platoons`
18. `"A comparison of spacing and headway control laws"`
19. `"Disturbance Propagation in Vehicle Strings" Seiler Pant Hedrick abstract`
20. `"String Instability in Classes of Linear Time Invariant Formation Control" abstract`
21. `"String stability of interconnected systems" 1996 IEEE abstract`
22. `"Adaptive cruise control design for active congestion avoidance" abstract`
23. `"Extending adaptive cruise control to adaptive driving strategies" abstract`
24. `"Empirical study on car-following characteristics of commercial automated vehicles" abstract`
25. `"Traffic Dynamics: Analysis of Stability in Car Following" abstract`
26. `"Dynamical model of traffic congestion and numerical simulation" abstract`
27. `"Full velocity difference model for a car-following theory" abstract`
28. `"A behavioural car-following model for computer simulation" abstract`
29. `"Multianticipative Piecewise-Linear Car-Following Model" abstract`
30. `"Empirics of Multianticipative Car-Following Behavior" abstract`
31. `"How reaction time, update time, and adaptation time influence the stability of traffic flow"`
32. `"Effect of adaptive cruise control systems on traffic flow" Davis 2004`
33. `"String Stability Conditions of Adaptive Cruise Control Algorithms" Wang Rajamani authors`
34. `"Driving towards stability and efficiency" "Abstract"`
35. `"String Stability Analysis and Design Guidelines for PD Controllers" authors abstract`
36. `"Stability and String Stability of Car-Following Models with Reaction-Time Delay" authors`
37. `"Unified framework for over-damped string stable adaptive cruise control systems" abstract DOI`
38. `"Response Time and Time Headway of an Adaptive Cruise Control" "Abstract"`
39. `"Car-Following Properties of a Commercial Adaptive Cruise Control System" authors`
40. `"Impacts of commercially available adaptive cruise control vehicles" "Abstract"`
41. `"Driving Characteristics and Adaptive Cruise Control" Schakel 2017`
42. `"OpenACC. An open database" abstract`
43. `"Car-following behavior characteristics of adaptive cruise control vehicles based on empirical experiments"`
44. `"The energy impact of adaptive cruise control in real-world highway multiple-car-following scenarios"`
45. `"Dissipation of stop-and-go waves via control of autonomous vehicles" abstract`
46. `"Will Automated Vehicles Negatively Impact Traffic Flow" abstract`
47. `"Fundamental diagrams of commercial adaptive cruise control" 103468`（初搜文章号猜错；最终由原文核实103458）
48. `"Effect of adaptive cruise control on fuel consumption in real-world driving conditions" authors abstract`
49. `"Mechanisms for spatio-temporal pattern formation in highway traffic models" abstract`
50. `"Vehicle platooning with constant spacing strategies and multiple vehicle look ahead information" abstract`
51. `"Model based string stability of adaptive cruise control systems using field data" doi`
52. `"Understanding widely scattered traffic flows" "016123"`
53. `"Multi-anticipative car-following model" "The microscopic" springer`
54. `"Practical String Stability" "Xiao" "Gao" 2011`
55. `"Multianticipative Piecewise-Linear Car-Following Model" "arxiv"`
56. `"String stability of heterogeneous platoons with non-connected automated vehicles" abstract`
57. `"Fundamental diagrams" "10.1016/j.trc.2021.103458"`

有些查询产生的新论文（例如无联网异质车队2017）最终没有收录，避免在未细读前增加条数。每篇保留的一手入口见papers.json；下列重点正文还保留可供复核的文本快照。

## 重点正文来源与本地文本（不是PDF批量下载）

| local_id | 文本文件 | 原始来源 | 已读重点 |
|---|---|---|---|
| A009 | gunter21.txt | https://lab-work.github.io/download/gunter2020commercially.pdf | Section II模型/定义、Section III实验 |
| A010 | gunter19.txt | https://arxiv.org/pdf/1902.04983 | Sections III–IV，实验剖面与标定 |
| A016 | li_fd21.txt | https://arxiv.org/pdf/2105.05380 | Sections 2.3、3.1平衡段筛选 |
| A019 | lowlevel21.txt | https://arxiv.org/html/2104.07726 | Sections 3.1–3.3低层误差/超调 |
| A020 | limits21.txt | https://arxiv.org/html/2108.03232 | Sections 3–5饱和、阶跃/周期与安全 |
| A021 | core22.txt | https://pmc.ncbi.nlm.nih.gov/articles/PMC9231564/ | Sections 2–5模型、Table1/2、频响/仿真 |
| A022 | multi_exp24.txt | https://pmc.ncbi.nlm.nih.gov/articles/PMC11573684/ | Section4.2.1/4.2.2、Table2统计检验 |
| A023 | hdm06.txt | https://www.akesting.de/download/HDM.pdf | Sections2.3–2.5，预瞄与平衡重标定 |
| A024 | trr07.txt | https://www.akesting.de/download/Timedelay_TRR_2007.pdf | pp.26–28，有限制动扰动与多前车截断 |
| A027 | idm10.txt | https://arxiv.org/pdf/0912.3613 | Sections2–4，切入、策略矩阵、容量 |
| A045 | cui17.txt | https://lab-work.github.io/download/Cui2017.pdf | SectionsII–V，线性化、反馈、持续噪声 |

`metadata_candidates.json`及小型抓取/编目脚本仅用于可追溯性，合并时应以`papers.json`和`synthesis.md`为主。源码未创建或执行任何新测试。无通信可迁移性与理论条件尚待root统一交叉核对。

末轮补核：已直接打开Springer的Lenz1999原始摘要，A025由metadata升为abstract；Makridis2020响应论文以JRC118223原作者机构摘要核实；Kesting2008以作者mtreiber.de原稿摘要核实。
