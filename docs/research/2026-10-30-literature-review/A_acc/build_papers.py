"""Manually curated reading records; not an automatic claim that search hits were read."""
import json
from pathlib import Path
P=Path(__file__).parent
papers=[]
STAMP='2026-10-29T17:22:20Z'
def add(title,authors,year,doi,url,summary,idea,limit,topic='ACC/string stability',info='sensing_only',fit='adaptable',level='abstract',locator='Abstract',**extra):
    papers.append(dict(local_id=f'A{len(papers)+1:03d}',title=title,authors=authors,year=year,doi=doi,primary_url=url,abstract_url=extra.pop('abstract_url',url),access_level=level,verified_utc=STAMP,topic=topic,abstract_summary_zh=summary,information_requirement=info,relevance=fit,transfer_idea_zh=idea,limitation_zh=limit,evidence_locator=locator,**extra))

add('String stability of interconnected systems','D. Swaroop; J. K. Hedrick',1996,'10.1109/9.486636','https://ieeexplore.ieee.org/document/486636',
 '已核对IEEE/Crossref书目与1996年卷页；IEEE原页触发机器人验证，未取得一手摘要。',
 '作为串稳定概念的原始书目入口，后续若作定理引用须另取得正文。','本记录不据二手摘要复述定理或证明。',info='unclear',fit='background',level='metadata',locator='IEEE/Crossref bibliographic metadata')
add('Constant Spacing Strategies for Platooning in Automated Highway Systems','D. Swaroop; J. K. Hedrick',1999,'10.1115/1.2802497','https://doi.org/10.1115/1.2802497',
 '已通过题名、作者、1999年与DOI交叉核对；本轮未取得出版社一手摘要或正文。','固定间距策略的历史书目入口；当前直接采用A053的可读原作者论述。','本记录仅元数据，不能据此给当前源码套用充分必要条件。',info='mixed',fit='background',level='metadata',locator='Bibliographic metadata; no primary abstract retrieved')
add('Intelligent cruise control systems and traffic flow stability','Swaroop Darbha; K. R. Rajagopal',1999,'10.1016/S0968-090X(99)00024-8','https://www.sciencedirect.com/science/article/pii/S0968090X99000248',
 '摘要明确区分车辆间距误差的串稳定与车辆加入/离开时密度、速度演化的交通流稳定。','把跟驰扰动衰减与3→2路段流量/行程评价分开。','两种稳定概念不同；局部串稳不能单独证明变车道交通提效。',fit='current_fit')
add('Optimal Adaptive Cruise Control with Guaranteed String Stability','Chi-Ying Liang; Huei Peng',1999,'10.1076/vesd.32.4.313.2083','https://www.tandfonline.com/doi/abs/10.1076/vesd.32.4.313.2083',
 '提出两层ACC：上层依据距离与距离变化率生成加速度，下层自适应伺服跟踪命令。','设计跟驰规则时同时明确命令与实际车辆响应模型。','属于特定两层控制综合；不能把理想上层结论直接赋予SUMO执行链。')
add('String Stability Analysis of Adaptive Cruise Controlled Vehicles','Chi-Ying Liang; Huei Peng',2000,'10.1299/jsmec.43.671','https://www.jstage.jst.go.jp/article/jsmec1997/43/3/43_3_671/_article/-char/en',
 '提出均质及混合车辆串的分析框架，并定义String-Stability Margin衡量ACC设计；以MATLAB和微观交通模拟说明。','除是否串稳之外，记录放大峰值或稳定裕量。','本轮PDF为扫描件且未OCR，阅读深度仅出版社摘要。')
add('Practical String Stability of Platoon of Adaptive Cruise Control Vehicles','Lingyun Xiao; Feng Gao',2011,'10.1109/TITS.2011.2143407','https://doi.org/10.1109/TITS.2011.2143407',
 '研究固定时距ACC的同质与异质车串，把传感器及执行器的寄生时延和惯性纳入纵向模型。','用实际跟踪滞后与观测延迟检查时距/增益，而非只看理想二阶模型。','尚未读全文条件；不能从摘要提炼数值下界。')
add('Disturbance propagation in vehicle strings','Pete Seiler; Aniruddha Pant; Karl Hedrick',2004,'10.1109/TAC.2004.835586','https://experts.umn.edu/en/publications/disturbance-propagation-in-vehicle-strings/',
 '以互补灵敏度积分解释仅相对间距、固定距离前车跟随的扰动放大限制，并研究前车跟随与双向结构的扰动到误差增益随规模变化。','固定30米方案应扫描车串长度与扰动频率，检验局部收敛后长串是否仍放大。','限制有明确控制结构假设；不能扩展成一切无通信控制均不可能。',fit='current_fit')
add('String Instability in Classes of Linear Time Invariant Formation Control With Limited Communication Range','Richard H. Middleton; Julio H. Braslavsky',2010,'10.1109/TAC.2010.2042318','https://ieeexplore.ieee.org/document/5406127/',
 '给有限前后信息范围的LTI车辆阵列串不稳充分条件，并用频响峰值下界联系间距策略、信息结构及车辆响应。','明确有限感知、刚性几何和响应速度之间的约束，避免只加邻车数量便宣称可扩展。','涵盖特定LTI与刚性/半刚性策略；当前切换、饱和系统需另分析。',info='mixed',fit='current_fit')
add('Are Commercially Implemented Adaptive Cruise Control Systems String Stable?','George Gunter et al.',2021,'10.1109/TITS.2020.3000682','https://lab-work.github.io/download/gunter2020commercially.pdf',
 '1200余英里数据标定7种2018款ACC，模型均串不稳；8车同款实验中领车6mph扰动增至尾车25mph。正文分开传感延迟二阶模型与执行器惯性三阶模型。','使用可重复领车扰动和多车串验证，并记录请求速度、实速与安全限速。','黑箱车款与特定实验不能代表所有ACC；模型本身是近似。',fit='current_fit',level='full_text',locator='pp.6994–6996, Section II model (3), definitions 1–2, Section III; abstract',abstract_url='https://arxiv.org/abs/1905.02108')
add('Model-Based String Stability of Adaptive Cruise Control Systems Using Field Data','George Gunter; Caroline Janssen; William Barbour; Raphael E. Stern; Daniel B. Work',2020,'10.1109/TIV.2019.2955368','https://arxiv.org/abs/1902.04983',
 '2015款电动车最短和最长跟车设置的拟合模型均串不稳；也显示有限长度车串能衰减部分特定扰动。实验覆盖18次、九类速度剖面。','单个扰动通过或短队看似平顺不能代替全频/长队稳定性。','读的是2019作者预印本，2020期刊书目由作者主页核对；无3→2横向过程。',fit='current_fit',level='full_text',locator='Author manuscript Sections III–IV, pp.7–10, abstract',version_note='2019 preprint read; 2020 journal identity verified at https://georgegunter.github.io/research/')
add('Impacts of commercially available adaptive cruise control vehicles on highway stability and throughput','Mingfeng Shang; Raphael E. Stern',2021,'10.1016/j.trc.2020.102897','https://www.sciencedirect.com/science/article/abs/pii/S0968090X2030797X',
 '比较文献理想ACC与实车标定ACC的SUMO混合流：理想参数最高增加7%瓶颈容量，商用参数部分情形下降35%；下游流量还受时距影响。','将同一交通场景下的跟驰参数作用与编队/横移作用严格消融。','数值是其IDM标定和渗透率场景结果，不可移植为本工程预期收益。',fit='current_fit')
add('Empirical Study on the Properties of Adaptive Cruise Control Systems and Their Impact on Traffic Flow and String Stability','Michail Makridis; Konstantinos Mattas; Biagio Ciuffo; Fabrizio Re; Akos Kriston; Fabrizio Minarini; Greger Rognelund',2020,'10.1177/0361198120911047','https://journals.sagepub.com/doi/10.1177/0361198120911047',
 '五车AstaZero试验测得控制器响应1.7–2.5秒，车串对不同扰动串不稳，轻微坡度变化也可诱发振荡。','把道路轻扰动和异质响应加入验收；避免将仿真步长当真实响应时间。','该响应范围只对应试验车辆与识别方法。',fit='current_fit')
add('Response Time and Time Headway of an Adaptive Cruise Control. An Empirical Characterization and Potential Impacts on Road Capacity','Michail Makridis; Konstantinos Mattas; Biagio Ciuffo',2020,'10.1109/TITS.2019.2948646','https://doi.org/10.1109/TITS.2019.2948646',
 '提出实际ACC响应时间和期望时隙的估计方法；特定控制器响应约0.8–1.2秒，与通常假设的人类驾驶量级相近。','区分测量响应时间、目标时距与数值更新时间。','不应把单车实测范围设成所有自动车辆的固定时延。',abstract_url='https://publications.jrc.ec.europa.eu/repository/handle/JRC118223')
add('OpenACC. An open database of car-following experiments to study the properties of commercial ACC systems','Michail Makridis; Konstantinos Mattas; Aikaterini Anesiadou; Biagio Ciuffo',2021,'10.1016/j.trc.2021.103047','https://arxiv.org/abs/2004.06342',
 '介绍开放跟驰试验库，预印本摘要涉及16辆车、其中11辆商用ACC，面向不同厂家实际运行特性。','可采用开放领车轨迹作统一外扰输入，少量代表轨迹已足够。','数据库版本和预印本统计范围有时间性；本轮未下载全库。',fit='current_fit')
add('Requiem on the positive effects of commercial adaptive cruise control on motorway traffic and recommendations for future automated driving systems','Biagio Ciuffo et al.',2021,'10.1016/j.trc.2021.103305','https://doi.org/10.1016/j.trc.2021.103305',
 '汇总JRC四轮实车测试，考察加减速分布、响应、时隙、串稳定、迟滞、能耗与安全；稳定初态本身难取得，坡度/转向可持续扰动。','评价全程成本与扰动后的恢复过程，不能用稳定几何截图替代交通效果。','原试验并非纯规则三车道自组织形成。',fit='current_fit',locator='Abstract and publisher Sections 5.1, 5.3 excerpts')
add('Fundamental diagrams of commercial adaptive cruise control: Worldwide experimental evidence','Tienan Li; Danjue Chen; Hao Zhou; Yuanchang Xie; Jorge Laval',2022,'10.1016/j.trc.2021.103458','https://arxiv.org/abs/2105.05380',
 '跨多地区实车数据比较ACC平衡间距–速度关系。正文用持续10秒、速度波幅≤0.45m/s、间距波幅≤1m等筛选平衡段，发现车型及头距设置显著改变基本图。','区分平衡容量潜力与扰动后实际瓶颈通行，不将30米/28.8m/s直接当全程容量。','本轮读2021作者稿，期刊为2022 TRC134:103458；DOI由NSF原文首页核实。',fit='current_fit',level='full_text',locator='Author manuscript Sections 2.3, 3.1.1, pp.4–6; abstract',version_note='2021 author manuscript read; 2022 TRC134:103458 corroborated by NSF manuscript https://par.nsf.gov/servlets/purl/10316424')
add('Car-Following Properties of a Commercial Adaptive Cruise Control System: A Pilot Field Test','Narayana Raju; Wouter Schakel; Nagarjun Reddy; Yongqi Dong; Haneen Farah',2022,'10.1177/03611981221077085','https://repository.tudelft.nl/record/uuid%3Afcca78a1-ec8a-48f8-a376-c69481534317',
 '荷兰两辆相同车的试验发现速度、间距设置和eco模式会改变跟驰指标，系统响应与人类响应时间相近。','使用不同速度/头距设置分层报告，避免只测单一巡航点。','小样本、单一车型；不是一般性串稳证明。',fit='background')
add('Driving Characteristics and Adaptive Cruise Control: A Naturalistic Driving Study','Wouter J. Schakel; Cornelis M. Gorter; Joost C. F. de Winter; Bart van Arem',2017,'10.1109/MITS.2017.2666582','https://repository.tudelft.nl/record/uuid%3A9dd99a6e-38cc-4598-813a-1925651c6654',
 '自然驾驶研究包含8名参与者，连续4–5周常规高速行程；以间距、头距、速度和加速度特征考察ACC效率影响。','将稳定跟驰与驾驶/交通模式分层，谨慎解释平均值。','自然驾驶与控制实验的因果解释不同；本轮只读仓库摘要。',fit='background')
add('Significance of low-level control to string stability under adaptive cruise control: Algorithms, theory and experiments','Hao Zhou; Anye Zhou; Tienan Li; Danjue Chen; Srinivas Peeta; Jorge Laval',2022,'10.1016/j.trc.2022.103697','https://arxiv.org/abs/2104.07726',
 '即使规划器串稳，慢速PI/PIF执行层仍可因相对速度误差积累导致超调，积分项还会增加实速超调；数值与真实车试验验证。','分别记录目标、渐近速度请求和执行速度，识别0.5秒响应与SUMO饱和如何改变传递。','读2021作者稿；其实车油门/制动模型与SUMO不同，不照搬PI增益。',fit='current_fit',level='full_text',locator='Author manuscript Sections 3.1–3.3, equations (13)–(19), Section 4; publisher journal identity')
add('Impact of Acceleration/deceleration Limits on the String Stability of Adaptive Cruise Control','Hao Zhou; Anye Zhou; Tienan Li; Danjue Chen; Srinivas Peeta; Jorge Laval',2021,None,'https://arxiv.org/abs/2108.03232',
 '加减速限制可使小信号串稳ACC在自然扰动下超调；不同车辆限制及排序会影响波动，制动限制也可能损害安全。','检验受5/10m/s²执行限制和安全裁剪后的真实扰动幅值，保留阶跃与周期扰动。','仅核实2021预印本；其线性规划器与本工程控制形式不同。',fit='current_fit',level='full_text',locator='Sections 3–5, especially 4.1–4.3 and Figures 5–10')
add('Multianticipation for string stable Adaptive Cruise Control and increased motorway capacity without vehicle-to-vehicle communication','Riccardo Donà; Konstantinos Mattas; Yinglong He; Giovanni Albano; Biagio Ciuffo',2022,'10.1016/j.trc.2022.103687','https://pmc.ncbi.nlm.nih.gov/articles/PMC9231564/',
 '以固定时距PD加入第二前车距离/速度反馈，不需加速度通信。解析和9600次随机参数仿真比较减振；第二车权重0.5为启发设置，250米视野丢目标时退回ACC。','在既有前200米同道观测内尝试第二实际前车反馈，先作为跟驰基线候选单独验证。','参数域和头距不覆盖现有(.6,2)、0.85秒；无3→2切换证明，雷达第二目标可靠性尚需实测。',fit='current_fit',level='full_text',locator='Sections 2.1–2.2 equations (1)–(4), Tables 1–2, Sections 3.1–3.3, 5.1–5.2')
add('Experimental investigation of the multianticipation mechanism in commercial SAE level 2 automated driving vehicles and associated safety impact','Riccardo Donà; Konstantinos Mattas; Sandor Vass; Biagio Ciuffo',2024,'10.1016/j.aap.2024.107784','https://pmc.ncbi.nlm.nih.gov/articles/PMC11573684/',
 '真实车辆存在第二前车反应，但主要是安全触发。21次干净扰动下ACC与MACC弱串稳中位数均>1；约10%改善的分布均值差检验p=0.1537，未排除同均值。','区分连续减振反馈与紧急多目标安全感知，不把感知能力直接认作串稳性能。','单一厂家及有限样本；2022理论控制器没有在此被原样实车验证。',fit='current_fit',level='full_text',locator='Section 4.2.1, Figure 10, Table 2; Section 4.2.2')
add('Delays, inaccuracies and anticipation in microscopic traffic models','Martin Treiber; Arne Kesting; Dirk Helbing',2006,'10.1016/j.physa.2005.05.001','https://www.akesting.de/download/HDM.pdf',
 'HDM把反应时延、相关估计噪声、时间与空间预瞄加入一般跟驰模型。多车作用直接求和会改变平衡间距，IDM情形给出重标定因子。','若加第二前车项，先校正平衡点，避免稳定性改善只是拉大间距造成。','主要人类驾驶元模型；不可直接把IDM重标定因子用于当前线性固定间距规则。',fit='current_fit',level='full_text',locator='Sections 2.3–2.5.1, equations (8)–(19), PDF pp.6–8')
add('Influence of Reaction Times and Anticipation on Stability of Vehicular Traffic Flow','Martin Treiber; Arne Kesting; Dirk Helbing',2007,'10.3141/1999-03','https://www.akesting.de/download/Timedelay_TRR_2007.pdf',
 '仿真区分局部稳定与更严格的串稳定，采用25m/s领车、-2m/s²持续3秒扰动及0.1秒更新；显式限制最大制动，预瞄数量不足时自然截断。','复用有明确初始平衡、有限制动与大扰动的检验思路，观察头车附近预瞄退化。','是2006 IFAC版本的扩展；不把两个版本算同一篇两次。',fit='current_fit',level='full_text',locator='pp.26–28, spatial anticipation and microscopic traffic simulations; Table 1')
add('Multi-anticipative car-following model','Henning Lenz; C. K. Wagner; Rudolf Sollacher',1999,'10.1007/s100510050618','https://link.springer.com/article/10.1007/s100510050618',
 '将Bando模型扩展为多车交互，响应多个前车使动力学稳定区域增大，同时描述自由流、拥堵及较紧密车串的同步流。','多车预瞄的历史机制依据；应与A023一起检查稳态间距是否改变。','只读Springer出版社摘要；不据此引用具体判据或增益。',topic='Multianticipation',fit='background',locator='Publisher abstract, lines 33–35')
add('Congested Traffic States in Empirical Observations and Microscopic Simulations','Martin Treiber; Ansgar Hennecke; Dirk Helbing',2000,'10.1103/PhysRevE.62.1805','https://arxiv.org/abs/cond-mat/0002177',
 '提出IDM并以德国高速实测边界再现车道封闭、坡道等不均匀处局部、延展与振荡拥堵；局部容量下降与匝道瓶颈可有近似影响。','跟驰动力学与瓶颈场景共同验证，不能只验证均匀直道。','定性拥堵结构重现不等于当前编队控制最优或串稳。',fit='background')
add('Enhanced intelligent driver model to access the impact of driving strategies on traffic capacity','Arne Kesting; Martin Treiber; Dirk Helbing',2010,'10.1098/rsta.2010.0084','https://arxiv.org/abs/0912.3613',
 '用恒加速度启发修正IDM切入小间隙时过猛制动。策略矩阵按局部交通状态调整头距/加速度，分别评价失稳前最大流量及堵后排出能力。','切入后暂态与正常跟驰应分别验收；交通效果按形成区/瓶颈分段。','它依赖前车加速度估计和IDM非线性结构，不建议整套替换当前简洁规则。',fit='adaptable',level='full_text',locator='Author manuscript Sections 2–4, Table 2, pp.2, 9–12')
add('Adaptive cruise control design for active congestion avoidance','Arne Kesting; Martin Treiber; Martin Schönhof; Dirk Helbing',2008,'10.1016/j.trc.2007.12.004','https://www.sciencedirect.com/science/article/pii/S0968090X08000028',
 '将ACC、局部交通状态识别与参数策略矩阵组合，在实测入口流驱动的匝道瓶颈模拟中提高稳定性/动态容量；通信是可选增强。','关注局部模式怎样改变纵向目标及瓶颈成本；保持无需通信的实现可能。','效果依赖特定策略矩阵、IDM和匝道案例，不直接迁移25%渗透率结论。',info='mixed',locator='Author manuscript abstract https://www.mtreiber.de/publications/ACC_TRC_final.pdf; publisher section snippets')
add('Effect of adaptive cruise control systems on traffic flow','L. C. Davis',2004,'10.1103/PhysRevE.69.066110','https://doi.org/10.1103/PhysRevE.69.066110',
 '线性串稳ACC仿真抑制全ACC车串扰动；混合交通结果依赖速度、车辆排序与ACC占比，匝道中收益可能有限。','异质响应及车辆排序应纳入稳定性敏感性检查。','线性理想ACC模型不能代表商用品或带切换的现控制器。',fit='background')
add('Empirical study on car-following characteristics of commercial automated vehicles with different headway settings','Xiaowei Shi; Xiaopeng Li',2021,'10.1016/j.trc.2021.103134','https://www.sciencedirect.com/science/article/pii/S0968090X21001534',
 '以实车数据标定简洁线性模型，较大头距设置倾向提高串稳定却降低机动/通行；控制敏感度随速度与设置改变。','用速度和头距网格报告性能，防止单一工作点的参数结论泛化。','线性拟合未覆盖非线性和随机性全部影响。',fit='current_fit')
add('Car-following behavior characteristics of adaptive cruise control vehicles based on empirical experiments','Tienan Li; Danjue Chen; Hao Zhou; Jorge Laval; Yuanchang Xie',2021,'10.1016/j.trb.2021.03.003','https://www.sciencedirect.com/science/article/pii/S0191261521000424',
 '三车实测显示ACC对振荡可放大或衰减、可出现超调或欠调，结果取决于头距、速度与领车刺激；多车传播可使波幅迅速加大。','把大/小幅、加速/减速、恢复阶段分开验证，避免只展示一种良好轨迹。','测试车型与刺激有限；不构成所有ACC统一定理。',fit='current_fit')
add('The energy impact of adaptive cruise control in real-world highway multiple-car-following scenarios','Yinglong He; Michail Makridis; Georgios Fontaras; Konstantinos Mattas; Hongming Xu; Biagio Ciuffo',2020,'10.1186/s12544-020-00406-w','https://link.springer.com/article/10.1186/s12544-020-00406-w',
 '在真实高速五车纵队比较人类与ACC跟驰，使用车轮牵引能量排除动力系统差异；明确处理坡度、切入、测量丢失等因素。','本工程燃油与纵向波动、分段成本联合评价；实测能耗定义不可混同SUMO fuel_abs。','公路条件难完全重复，原文能量指标不是发动机燃油。',fit='current_fit',locator='Abstract; publisher Section 2.1–2.2 excerpts')
add('Car-following models: fifty years of linear stability analysis – a mathematical perspective','R. E. Wilson; J. A. Ward',2011,'10.1080/03081060.2011.530826','https://eprints.soton.ac.uk/id/eprint/184225',
 '统一线性稳定分析框架，区分均匀流、platoon与string stability，并细分绝对与上/下游对流不稳。','编队关系0/1、几何误差收敛与扰动不放大应分属不同证据。','只读作者仓库摘要；不据摘要引用具体判据。',fit='current_fit')
add('Mechanisms for spatio-temporal pattern formation in highway traffic models','R. E. Wilson',2008,'10.1098/rsta.2008.0018','https://www.mat.univie.ac.at/~wpi/themedata/Motility_Workshop/Wilson.pdf',
 '综述高速交通图样的相互竞争解释，并以动力系统和双稳态机制分析交通波。','允许相同平均流量在不同初态下演化成不同交通状态，验收应保存不利轨迹。','背景理论，不能作为当前多车道形成控制的证据。',fit='background',locator='Abstract in university-hosted original paper')
add('Full velocity difference model for a car-following theory','Rui Jiang; Qingsong Wu; Zuojin Zhu',2001,'10.1103/PhysRevE.64.017101','https://doi.org/10.1103/PhysRevE.64.017101',
 '以解析与数值方法研究同时包含完整速度差作用的跟驰模型，可描述相变和拥堵演化。','保留相对速度反馈作为局部减振机制，并考察它与位置增益的关系。','出版社摘要没有提供当前增益的可直接应用判据。',fit='background')
add('A behavioural car-following model for computer simulation','P. G. Gipps',1981,'10.1016/0191-2615(81)90037-0','https://www.sciencedirect.com/science/article/pii/0191261581900370',
 '根据驾驶员对期望制动与加速度的限制构造跟驰模型，参数对应可解释行为特征，并以仿真重现实交通。','解释安全制动层与期望跟驰层各自作用，比较制动约束对波动的影响。','本工程停止位置安全式与Gipps原式不能未经推导混写。',fit='background')
add('Understanding widely scattered traffic flows, the capacity drop, and platoons as effects of variance-driven time gaps','Martin Treiber; Arne Kesting; Dirk Helbing',2006,'10.1103/PhysRevE.74.016123','https://arxiv.org/abs/physics/0508222',
 '用局部速度方差驱动的时距适应描述流量散布、容量下降与platoon；虚拟检测器输出与荷兰A9实测作半定量比较。','可把局部速度不一致作为扩大暂态间距的简洁指标候选。','增加状态依赖时距会改变交错几何，原文人类适应规则没有保证当前串稳。')
add('Multianticipative Piecewise-Linear Car-Following Model','Nadir Farhi; Habib Haj-Salem; Jean-Patrick Lebacque',2012,'10.3141/2315-11','https://doi.org/10.3141/2315-11',
 '将分段线性跟驰扩展至多前车，研究均质情形的稳定与稳态；保持宏观稳态行为同时缓和暂态速度/加速度方差，并以NGSIM识别参数。','第二前车机制首先验证平衡点未改变，再比较暂态减振。','均质模型和分段线性结构与当前混合切换不同。',locator='Publisher abstract https://journals.sagepub.com/doi/10.3141/2315-11')
add('Evidence on impacts of automated vehicles on traffic flow efficiency and emissions: Systematic review','Elina Aittoniemi',2022,'10.1049/itr2.12219','https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/itr2.12219',
 '系统综述非联网自动车：仿真常研究理想潜力；商用ACC实测和标定仿真在高流量下可能降低效率。指出模型、道路、车群构成与时距假设造成可比性问题。','文献结论标注感知边界与共同基线，以全车群交通效果而非装备车单车表现为目标。','综述提供证据地图；具体机制仍引用原始研究。',info='mixed',fit='current_fit')
add('Effect of adaptive cruise control on fuel consumption in real-world driving conditions','Ayman Moawad; Matthew Zebiak; Jihun Han; Dominik Karbowski; Yaozhong Zhang; Aymeric Rousseau',2024,'10.1038/s41467-024-54066-8','https://www.nature.com/articles/s41467-024-54066-8',
 '对大型自然驾驶数据作行程与事件分层的混合效应分析；控制协变量后整体ACC油耗约增加0.26L/100km，效果随速度及有无前车变化。','燃油收益须与速度、跟驰/巡航及加减速事件共同解释，避免单一平均收益叙述。','观察研究依赖控制混杂假设；实车油耗单位与SUMO指标不直接比。',fit='background',locator='Publisher results/methods excerpts; OSTI original-paper title page and abstract')
add('Driving towards stability and efficiency: A variable time gap strategy for Adaptive Cruise Control','Shaimaa K. El-Baklish; Anastasios Kouvelas; Michail Makridis',2025,'10.1016/j.trc.2025.105074','https://doi.org/10.1016/j.trc.2025.105074',
 '固定平衡时距加受反馈调节的变动分量，以非线性H∞设计减扰，使用OpenACC及SUMO评估，讨论执行滞后和输入延迟鲁棒性。','借用稳态紧凑、扰动态放松的目标设计思想，不必引入完整H∞求解器。','其保证依赖特定非线性反馈和参数，不可把任意启发式变时距冠以串稳。',locator='ETH author abstract; publisher Sections 1.2, 5.2 excerpts',version_note='2024 arXiv2402.14110; 2025 journal DOI verified')
add('String Stability Analysis and Design Guidelines for PD Controllers in Adaptive Cruise Control Systems','Kangjun Lee; Chanhwa Lee',2025,'10.3390/s25113518','https://www.mdpi.com/1424-8220/25/11/3518',
 '给均质纵向动力学与固定时距PD的个体/串稳定增益设计步骤，先选响应所需比例增益再调导数增益。','简洁PD仍有分析价值；先给出车辆模型和时距定义再做增益选择。','本轮读摘要及Section4片段，不能声称全文核验其所有不等式。',fit='current_fit',locator='Abstract; Section 4 design and 4.1 excerpts')
add('Stability and String Stability of Car-Following Models with Reaction-Time Delay','Guy Fayolle; Jean-Marc Lasgouttes; Carlos Flores',2022,'10.1137/21M1443650','https://epubs.siam.org/doi/abs/10.1137/21M1443650',
 '对有反应时延的跟驰线性化传递函数给出稳定性条件，区分稳定、串稳定和仅在临界频率以下不放大的部分串稳定。','多频率扰动验收，防止低频通过掩盖高频放大。','作者给定反应延迟结构下的结论，不可把时延等同采样步长。',fit='current_fit')
add('A Nonlinear CTH-Based Adaptive Cruise Controller With Safety and String Stability Guarantees','Dionysios Theodosis; Amirhossein Samii; Nikolaos Bekiaris-Liberis',2026,None,'https://arxiv.org/abs/2607.24228',
 '异质车辆的非线性固定时距控制，使用速度相关增益和饱和非线性限制速度/加速度；从闭环动力学证明无碰撞区域正不变及Lp串稳定充分条件。','说明饱和、安全与串稳应在同一非线性模型下共同分析的路线。','截至检索日为新预印本，仅读摘要，不能照搬尚未阅读全文的定理。',fit='background')
add('Stabilizing Traffic Flow via a Single Autonomous Vehicle: Possibilities and Limitations','Shumo Cui; Benjamin Seibold; Raphael Stern; Daniel B. Work',2017,None,'https://lab-work.github.io/download/Cui2017.pdf',
 '一般二阶跟驰线性化给出速度扰动传递函数；理想无噪环路可由低比例控制车稳定，但引入噪声揭示稀疏控制限制。','对当前规则先分析无换道单链的传递，再加入噪声和连续注入扰动。','环路近均衡设定且需估计平衡速度；不能作为开放3→2道路的成队/容量保证。',info='mixed',fit='current_fit',level='full_text',locator='Sections II–V, equations (1)–(17), PDF pp.2–6')
add('Dissipation of stop-and-go waves via control of autonomous vehicles: Field experiments','Raphael E. Stern et al.',2018,'10.1016/j.trc.2018.02.005','https://arxiv.org/abs/1705.01693',
 '20余车环形跑道的实验证明控制一辆车可以耗散人类引起的停走波，比较速度、制动及燃油。','采用简单局部减振控制和明确外扰、全车指标，而不是先追求复杂优化器。','原文明确不研究换道或几何瓶颈，不能由其推断3→2合流提效。',info='mixed',fit='adaptable')
add('Will Automated Vehicles Negatively Impact Traffic Flow?','Simeon C. Calvert; Wouter J. Schakel; J. W. C. van Lint',2017,'10.1155/2017/3082781','https://onlinelibrary.wiley.com/doi/10.1155/2017/3082781',
 '讨论初期自动化较大时距可能对混合流不利，而更一致的动态可能有益；换道效应研究不足。','对额外补位换道引起的扰动、空隙成本做独立归因。','条件性交通影响讨论不能替代当前参数的实测消融。',info='mixed',fit='background',locator='Abstract and Section 2.2.5 excerpts')
add('Modeling cooperative and autonomous adaptive cruise control dynamic responses using experimental data','Vicente Milanés; Steven E. Shladover',2014,'10.1016/j.trc.2014.09.001','https://www.sciencedirect.com/science/article/pii/S0968090X14002447',
 '同四辆生产车比较商用ACC、自研CACC与IDM实现；ACC放大前车速度变化，CACC较平滑，实车响应标定模型用于微观仿真。','把执行层真实响应纳入模型；通信增强结果只作背景，不能移植到无通信规则。','CACC需要V2V；其可用信息超出现有系统。',info='mixed',fit='background')
add('Unified framework for over-damped string stable adaptive cruise control systems','Parthib Khound; Peter Will; Antoine Tordeux; Frank Gronwald',2023,'10.1016/j.trc.2023.104039','https://www.sciencedirect.com/science/article/pii/S0968090X23000281',
 '针对同质车串综合补偿执行惯性、传感延迟和输入扰动，要求过阻尼串稳以避免超调/欠调，适用于线性或凸的速度相关间距函数。','将单次大扰动超调和频域能量放大同时作为验收目标。','需滑模、Smith预测器和扰动观测器，超过本轮简洁规则迁移范围。',fit='background')
add('Car-Following Characteristics of Commercially Available Adaptive Cruise Control Systems and Comparison With Human Drivers','Yingjun Ye; Jie Sun; Jian Sun',2023,'10.1177/03611981221113313','https://journals.sagepub.com/doi/10.1177/03611981221113313',
 '以OpenACC比较多个系统与人类，从五个模型选择IDM拟合，并评估混合分布差异及仿真串稳定；测试ACC均串不稳且车型差异明显。','参数异质性不能仅用一辆代表车替代；稳定性模型选择也影响结论。','结果依赖数据、拟合模型与模拟条件，非对所有ACC的普遍定理。',fit='background')
add('Validating car-following behaviors of autonomous vehicles by structural assessment with empirical data','Jingbiao Huo; Ke Ma',2026,'10.1007/s44285-026-00080-9','https://link.springer.com/article/10.1007/s44285-026-00080-9',
 '自然驾驶轨迹校准同时识别感知/决策反馈时延与执行寄生惯性，并容纳线性固定时距和非线性IDM结构。','显式区分观测延迟与本车速度渐近响应，检查本工程0.5秒响应近似。','2026新文，仅读出版者摘要片段，不引用具体数值或定理。',fit='adaptable')
add('Empirical Analysis of a Generalized Linear Multianticipative Car-Following Model in Congested Traffic Conditions','Xiao Zhang',2014,'10.1061/(ASCE)TE.1943-5436.0000667','https://ascelibrary.org/doi/abs/10.1061/%28ASCE%29TE.1943-5436.0000667',
 'NGSIM多前车线性模型识别强调解释变量多重共线性、时间序列自相关及反应时延识别会影响多预瞄参数估计。','若实测/仿真识别第二前车收益，避免把同一波动下的高度相关信息误当独立因果贡献。','属于经验辨识，不能证明当前控制器串稳。',fit='background')
add('Vehicle platooning with constant spacing strategies and multiple vehicle look ahead information','Swaroop Darbha; Shyamprasad Konduri; Prabhakar R. Pagilla',2020,'10.1049/iet-its.2019.0204','https://ietresearch.onlinelibrary.wiley.com/doi/abs/10.1049/iet-its.2019.0204',
 '在寄生惯性车辆模型下证明一类固定间距、有限r前车反馈的串不稳，含静态/动态间距反馈；另讨论有leader/predecessor信息时的有限队列增益选择。','第二前车观测不能自动挽救固定30米长串；先明确时距/信息结构与车辆模型。','不能泛化到所有非线性、绝对状态反馈与切换控制；LPF部分需要额外队首信息。',info='mixed',fit='current_fit',locator='Publisher full Introduction, contributions (i)–(ii), Sections 2–4 outline')

assert len(papers)==53
(P/'papers.json').write_text(json.dumps(papers,ensure_ascii=False,indent=2),encoding='utf8')
print('Records:',len(papers))
from collections import Counter
print('Reading depth:',Counter(p['access_level'] for p in papers))
print('Information:',Counter(p['information_requirement'] for p in papers))
