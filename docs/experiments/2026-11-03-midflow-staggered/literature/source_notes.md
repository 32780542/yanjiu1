# 一手来源与可迁移的有限结论

核查日期：2026-11-03。先读取`docs/research/2026-10-30-literature-review/papers.json`，再定向补核，未重做150篇泛搜。下面的“启示”是本项目推断，不是原论文已经证明本项目算法有效。没有引用搜索营销稿、代投指南或期刊排名数据。

## 期刊实际上要求什么

**J1，Transportation Research Part C，出版商官方scope。** 已浏览[Elsevier官方期刊说明](https://shop.elsevier.com/journals/transportation-research-part-c-emerging-technologies/0968-090X)，定位Description第85–89行。其核心要求是技术对交通系统运行、效率、安全、可靠性、资源消耗等的影响；并重视支持迁移和基准比较的开放数据。ScienceDirect的[当前Guide for Authors](https://www.sciencedirect.com/journal/transportation-research-part-c-emerging-technologies/publish/guide-for-authors)及scope页本次403，**未据此宣称已核实具体字数、上传清单或所有格式规定**。

**J2，IEEE Transactions on Intelligent Transportation Systems。** 已浏览[ITSS当前官方期刊页](https://ieee-itss.org/pub/t-its/)，定位Scope及Our Authors’ Guidelines。该刊要求清楚展示交通系统应用及收益；摘要须自足、准确覆盖全文，150–250词。会议论文扩展须说明实质新增分析、理论或实验。此处“T-ITS”是智能交通系统期刊。官方scope中的车辆交互不能被误读为算法必须使用V2V。

由J1/J2推导出的本项目写作标准：标题的问题、方法的局部信息假设、机制图、消融和结论必须对齐；图形漂亮或编队完整不自动等于交通收益。这是研究叙事建议，不是期刊公布的量化录用门槛。稿件是否接收仍由真实同行评审决定，官方指南没有给出“故事好即可录用”的承诺。

## 直接有关的五组研究

| 来源 | 与本地目录关系 | 本次实际取得范围 | 可引用的有限事实 | 对本项目的启示/边界 |
|---|---|---|---|---|
| Cai等，*Formation control for connected and automated vehicles on multi-lane roads: Relative motion planning and conflict resolution*，IET ITS，17(1)，211–226，2023；[DOI](https://doi.org/10.1049/itr2.12249)，[作者全文](https://arxiv.org/html/2103.10287v3) | L055；另L054是2024混行扩展 | 浏览作者全文§II–IV；Wiley入口超时 | 上层联合分配交错目标并消解冲突，下层跟踪分段时空轨迹；预留空位服务队形变换 | 可继承局部间隙几何；不能将集中目标分配称作无通信分布式方案。2024原文和本机实现另见cai_transfer。 |
| Woo、Skabardonis，*Flow-Aware Platoon Formation of Connected Automated Vehicles in a Mixed Traffic with Human-driven Vehicles*，TRC，133，103442，2021；[DOI](https://doi.org/10.1016/j.trc.2021.103442)，[作者全文](https://arxiv.org/html/2108.05530v1) | L099，已有全文项 | 浏览§3、§4.2、§6 | 主动组织换道可能降低容量；其Flow-Aware门使用附近检测器的平均流量和速度，阈值按网络/渗透率校准 | 组织活动应服务可执行交通任务；检测器流量和原阈值不能直接进入本项目控制器。论文没有证明本项目的无通信条件触发。 |
| Rupp、Stolz、Horn，*Decentralized Cooperative Merging using Sliding Mode Control*，IFAC-PapersOnLine，51(9)，349–354，2018；[DOI](https://doi.org/10.1016/j.ifacol.2018.07.057)，[出版社摘要](https://www.sciencedirect.com/science/article/abs/pii/S2405896318307808) | L121，已有摘要项 | 出版社索引返回完整摘要；直接正文入口403；[作者机构记录](https://tugraz.elsevierpure.com/en/publications/decentralized-cooperative-merging-control-for-lane-reduction-scen/)为会议记录，标题略长 | 摘要明确已有lane reduction场景、无车间通信、编队/拓扑选择与滑模控制 | 足以阻止“首次无通信协同合流”的草率首创声明；不足以复述其滑模律、可感知范围、切换规则或定理。正文获取仍是相关工作缺口。 |
| Scholte、Zegelaar、Nijmeijer，*A control strategy for merging a single vehicle into a platoon at highway on-ramps*，TRC，136，103511，2022；[DOI](https://doi.org/10.1016/j.trc.2021.103511)，[作者机构全文](https://pure.tue.nl/ws/portalfiles/portal/195066067/1_s2.0_S0968090X21004952_main.pdf) | 本地150篇未列此题/DOI；L124是相关的2025实验论文，不能混为同篇 | 浏览机构PDF；本地另抽取全文并查看图1 | 后车先开隙，再跟踪并入车构成虚拟CACC，同时保留对原前车的安全控制。§3.1预设可行三车组，不解决合流排序；§3.2/3.6需要共享信息/通信 | 支持“接收车提前响应跨道并入车”的机制动机；三车组识别、无通信和余距可行性必须自行建立，不能继承原稳定性结论。 |
| Chen、Wang、Gong、Zhou、Ran，*Connected and Automated Vehicle Distributed Control for On-ramp Merging Scenario: A Virtual Rotation Approach*，TRC，133，103451，2021；[DOI](https://doi.org/10.1016/j.trc.2021.103451)，[作者PDF](https://arxiv.org/pdf/2103.15047)，[版本信息](https://arxiv.org/abs/2103.15047)，[作者机构书目](https://yangzhou.engr.tamu.edu/publications/) | 本地150篇未列此题/DOI | 浏览作者PDF第3–7页，arXiv v2于2022-01-18更新；卷号另核作者机构书目 | §2明确集中决定虚拟车辆顺序；随后用V2V/V2I、多前车反馈及加速度前馈控制，分析其串稳定性 | “distributed”不等于无全局信息。可借鉴把合流关系变成虚拟跟驰；其排序、前馈和理论不能直接移植。 |

以上每篇只支持表内限定内容。特别是Rupp的摘要证据不能升级为已逐式复现的全文证据；Scholte和Chen的通信设计也不是本项目的无通信实现。

## 本次检索没有建立的结论

没有穷尽所有无通信编队文献，因此不能宣布全世界不存在与本项目相同的局部拓扑方法；没有核查足够实车证据，因此不能写已适用于部署；没有运行与这些论文相同的场景，因此不能做跨论文百分比排名。Nature写作社论的本次直接访问遇到登录跳转，未把它们作为本文件独立核实的依据。

下一步文献工作应优先取得Rupp正文，逐项比较其邻车集合、拓扑切换、lane-drop几何和信息假设；不必再扩充一大批只有题名关系的论文。
