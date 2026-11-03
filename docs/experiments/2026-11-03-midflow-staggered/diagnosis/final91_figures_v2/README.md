# 最终三流量全种子效应图

两图数据只来自已完成90例原件/raw/ledger独立核验，来源[SHA索引](source_sha256.json)及[全部绘图数值](plot_data.json)。每图90个观察点，五种子91–95全部显示；均值为种子等权，不按车辆数池化，无置信区间或显著性标注。

- [完整请求系统时间：300dpi PNG](final91_system_time_effects.png) / [SVG](final91_system_time_effects.svg)
- [完整请求燃油：300dpi PNG](final91_fuel_effects.png) / [SVG](final91_fuel_effects.svg)
- [NOA/D1/S绝对系统时间简表](absolute_system_time.md) / [五种子完整CSV](absolute_system_time.csv)

图注：列为1500、1750、2000辆/h/车道，上排D1−NOA、下排D1−S。各格显示直路差、缩道差和绝对道路DID；同种子两道路点相连，DID单独显示，黑横线为五种子均值，虚线为0。负值表示对应指标更低；道路DID是缩道差减直路差，不是百分比之差。各行共享y轴范围，行间范围独立。需求600s、统一1200s排空上限，全部请求计入。系统时间下降与耗油增加可同时成立；原S接收后车制动代价的机制限制另行报告。

PNG分别3644×2248、3612×2248，PIL实际DPI299.9994，SVG保留矢量和可编辑文字。两图已重新逐张视觉检查：全部种子点可见，图例、两行注释分离，无底部重叠或裁切。[视觉与哈希QA](visual_qa.json)。v1保留初稿及其footer重叠，不作为定稿。
