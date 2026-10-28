# 阶段5D：主从博弈与分布式换道文献筛选

检索日期2026-09-13。结论是**可以研究局部博弈，但须把预测邻车响应和实际安全准入分开**。本轮沿用用户此前的无隐含通信、无车型真值、无全局调度约束；“分布式”并不自动意味着无需通信或无需邻车效用参数。

以下只依据论文原文、作者机构仓储或出版社摘要。不是系统综述，也不宣称穷尽最新论文。完整独立审读、页码、PDF SHA和访问失败见[独立笔记](D:/yanjiu1/keyan1/docs/phase5d_independent_literature_notes.md)。表中“适用判断”是本项目推断，并非作者对本项目的结论。

Hang及两篇Yoo原PDF另已保存至[三篇原始来源归档](D:/yanjiu1/keyan1/results/phase5d/primary_archive_20260913T111008400597Z/manifest.json)，含URL、UTC、文件/抽取SHA和读取范围。[归档日志](D:/yanjiu1/keyan1/results/operations/20260913T111006853716Z_phase5d_primary_literature_archive_21e71a8d/result.json)退出0；PDF抽取警告保留。早期隔离解释器缺包/TLS失败尝试同样保留，后用已安装requests及证书包完成TLS验证下载。归档全部页面不等于已逐页审读，表中范围不变。

|论文|读到的证据与适用判断|
|---|---|
|Hang, Lv, Xing, Huang, Hu，*Human-Like Decision Making for Autonomous Driving: A Noncooperative Game Theoretic Approach*，arXiv 2020 / IEEE T-ITS 2021|[作者预印本](https://arxiv.org/abs/2005.11064)。已核摘要及PDF第4–6页成本、风格权重和式17；把换道与纵向加速度结合，给出下层最优响应集合和上层对多响应的悲观选择。可借鉴双层结构，不能把预设风格权重当成局部传感器获得的真实参数，也不能移植其场景中的成本改善为本项目收益。|
|Yoo, Langari，*A Game-Theoretic Model of Human Driving and Application to Discretionary Lane-Changes*，arXiv 2020|[作者预印本](https://arxiv.org/abs/2003.09783)。已核摘要、问题设置和PDF第6–7页求解与多解处理。每车根据自己的模型预测其他车；正文主动承认不共享效用时，预测的最优响应不保证发生。适合支持“本车内部条件模型”定位，不能称实际共同均衡或已完成定量验证。|
|Yoo, Langari，*A Stackelberg Game Theoretic Model of Lane-Merging*，arXiv 2020|[作者预印本](https://arxiv.org/abs/2003.09786)。已核摘要与PDF第2–4页邻域识别、车辆模型和合流设置，未声称逐页完整审读。把合流前加/减速纳入动作，适合提示应检查等待纵向行为。激进程度和反应/识别参数属于模型设定，不是本项目可直接读取的车型/意图真值。|
|Geary, Ramamoorthy, Gouk，*Resolving Conflict in Decision-Making for Autonomous Driving*，RSS 2021|[会议全文](https://www.roboticsproceedings.org/rss17/p049.pdf)，独立读完11页。它直接分析双方对主从角色理解不一致；利他修正仍有收益/双方参数已知等假设。本项目保留可见几何角色，并明确它是本车建模方向，不能声称双方已经同意。|
|Wang, Wang, Talbot, Gerdes, Schwager，*Game Theoretic Planning for Self-Driving Cars in Competitive Scenarios*，RSS 2019|[会议全文](https://www.roboticsproceedings.org/rss15/p48.pdf)，独立读完9页。无显式车间通信、内部迭代最优响应，但采用Nash近似；收敛结论有条件，实际仅迭代两轮。可借鉴本车内部计算方式；试验定位条件强于本项目，不能用作有限局部感知或主从均衡的验证。|
|Li, Kolmanovsky, Girard, Yildiz，*Game Theoretic Modeling of Vehicle Interactions at Unsignalized Intersections and Application to Autonomous Vehicle Control*，ACC 2018|[大学仓储全文](https://repository.bilkent.edu.tr/server/api/core/bitstreams/b9f35899-5528-40c4-ba4a-52a946eba854/content)，独立读完6页。有限动作与自有信念更新可作未来备选；研究对象为无信号路口，不是本轮换道。保留作者场景中的失败，不能移植其有限碰撞惩罚来替代原守卫。|
|Bouzidi, Hashemi，*Interaction-aware motion planning and control based on game theory with human-in-the-loop validation*，RAS 186 (2025),104908|[出版社摘要](https://www.sciencedirect.com/science/article/pii/S0921889024002926)。只取得摘要/Highlights，未取得全文；无通信效用估计可作后续检索线索，本轮不根据未读公式实现或声称其保证适用。|

另查Ye等2022年的[换道博弈论文](https://www.mdpi.com/1424-8220/22/18/6729)，出版社可读摘要/方法检索文本明确使用完全信息非合作博弈，并在交互描述中采用转向灯或小幅横向动作。正文访问遇到验证/错误页，未保存完整可审读正文。因此本轮不复制它的信号交互或完全信息假设。

本轮比较采用两个有实质区别的本地求解方法：有限模型分支的minimax，与对方模型leader/本车follower的悲观Stackelberg。令a为本车请求、b为对方假想动作，先求`BR_E(b)=argmin_a J_E(a,b)`，再求`b*=argmin_b max_{a∈BR_E(b)} J_P(a,b)`；实际只申请执行本车的a。minimax直接求`argmin_a max_b J_E(a,b)`，不与双层求解混称。

两种方法都保留5C原换道准入、最低速度及全邻车可达守卫，按同一冻结场景比较。模型时域、动作集、成本权重、角色触发和回退已写入[预登记计划](D:/yanjiu1/keyan1/docs/phase5d_local_game_plan.md)。这是文献启发的新有限模型，**不是对任何一篇论文完整复现**。若守卫拒绝模型请求并回退，必须分别记录模型选择和实际请求；不得计为“均衡已执行”。

5C已经表明低速门槛与形成增量守卫是独立障碍。文献筛选没有消除这些失败条件；新实验即使少减速，也不自动构成阶段5科学通过。
