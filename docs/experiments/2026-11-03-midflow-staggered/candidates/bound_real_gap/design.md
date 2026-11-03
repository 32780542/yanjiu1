# GP最小设计（构建前）

从冻结S单独出发，仅在transform地图准备区对初次/active目的lane1统一规划，目的lane0、NOA、formation及直路保持原规则。不叠V/F/C5源码。

唯一规划对象是本车可见的真实目标走廊相邻F/R。令Traw=(drop_x−ego.x)/CRUISE−原横移1s，Traw≤0不规划；否则T=max(.1,Traw)。F/R名义恒速，终速u为原F/R均速，D(v)=LENGTH+STANDSTILL+HEADWAY*v。终点区间为[R.x+R.v*T+D(R.v), min(F.x+F.v*T−D(u), drop_x−u*1s)]。

把该窗换为D=X−ego.x−ego.v*T，与cubic加速度端点[-10,+5]及全程速度[0,33.3]的解析D区间求交。J=12D²/T³−12DE/T²+4E²/T，E=u−v；将D*=E*T/2解析clip至交集，不做扫描。选择J最小的可达pair；已经持有的真实pair只要仍可见、有序、相邻、名义可达就优先保持，即使ego尚未位于F/R之间。无可达双侧资源，恢复原当前gap策略，不等待或制造gap。

同一pair同时生成本步min∫a²初始加速度和memory.gap。新横移请求要求ego已处于该pair实际区间且原_clear通过。必要merge、active lane_target1及初次freefill目标1统一接此对象；freefill目标0保持原执行。自身Memory仍只有lane_target/gap/joining。

T是逐帧名义时域，不是首次承诺后的deadline；恒速预测、道路余距和解析名义边界不构成实际执行安全/完成保证。横移已经被SUMO启动时，本车不能靠拒发新命令撤销其原执行。测试先检查压缩当前gap被跳过、held在区间外保留、错误gap不启动横移、资源不足/范围外严格回退、标签/排列/感知外不干扰、原物理安全，以及cubic约束的独立数值交叉核对。
