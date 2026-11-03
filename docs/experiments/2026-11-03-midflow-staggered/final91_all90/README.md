# 最终90例：主D1−NOA、次D1−原S

90独立run全部安全排空、原件/需求/物理/五非规则源/协议90/90通过，60对全部有效。原summarize reference D产生30个D1−NOA与30个S−D1；次表显式交换两侧并反号为D1−S，资格不变，原paired.csv与[转换证明](analysis/secondary_direction_derivation.json)均保留。真实输入组30个，91–95仅五种子；不把配对/案例数称种子数。

| 每道流量 | 道路 | D1−S系统(s) | 逐种子百分比均值(%) | 更快种子 | 燃油差(g/km) |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1500 | lane_drop | -0.179288 | 0.425668 | 5/5 | -0.161456 |
| 1500 | straight3 | -0.096089 | 0.231314 | 5/5 | -3.102072 |
| 1750 | lane_drop | -0.255005 | 0.597787 | 5/5 | -0.825592 |
| 1750 | straight3 | -0.109491 | 0.263678 | 5/5 | -3.827496 |
| 2000 | lane_drop | -0.582096 | 1.319394 | 5/5 | -2.802182 |
| 2000 | straight3 | -0.109768 | 0.264221 | 5/5 | -4.315308 |

| 每道流量 | 次比较道路DID(s) | 额外缩道更好种子 |
| ---: | ---: | ---: |
| 1500 | -0.083199 | 5/5 |
| 1750 | -0.145514 | 5/5 |
| 2000 | -0.472328 | 4/5 |

次比较30对系统时间全部更快；15个次DID有一个反向，仍完整保留。正式次逐种子见[secondary_D1_minus_S.csv](analysis/secondary_D1_minus_S.csv)及[secondary_DID_paired_seeds.csv](analysis/secondary_DID_paired_seeds.csv)，所有反例见[secondary_nonimprovements.json](analysis/secondary_nonimprovements.json)。主表在[final91_D1_NOA60](../final91_D1_NOA60/README.md)，上述百分比为mean_of_paired_percent，旧ratio_of_means另列不覆盖。

直接本车0/1来自90份原result.formation_state并绑定逐result SHA：[formation_per_case_from_result.csv](analysis/formation_per_case_from_result.csv)、[五种子等权18组](analysis/formation_seed_equal_means.json)、[范围定义](analysis/formation_scope.json)。参与车辆秒比例、全场均/峰参与人数、episodes和连续1均/最长时长均沿原字段，每组是五个case字段等权均值，非episode合池；峰值列为五个case峰值的均值。NOA参与量/人数/episodes全0，无episode时原mean/max_episode为null/N/A，不擅填0。1允许调距，不表示完整几何队形或一支编队大小；语义与实际几何分别报告。

源在最终输入前固定，所有不改善指标/病例/坏seed均保留，不改D1。全90raw审计/所需post5提取及root清理计划审查前不删。四个完整道路包分别在主60和S30目录，本文无重跑或重复计数。
