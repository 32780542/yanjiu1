# BC：同容量参考、无主动交错组织

主任务批准BC作为B的匹配对照，单独命名，不等同于原纯NOA。只读已锁定B源（SHA `7d749ba8919efbf06efc0abd43846dee4c13b886e81019ae89c0f0116a1553d2`）。B本体不改。

保留B的45m基础组织CTH参考、90m真实side-witness前车关联及其地图适用范围。控制器全程去除phase速度反馈和自由`_fill`发起；所有输出formation_state为0。transform在缩道或直路均可使用原NOA的慢前车普通超车规则。原实际mode=noa逐位保持冻结S。已有active/pending横移、必要合流及真实gap执行保留，未增加等待/门禁/安全阈值。

TDD先用冻结B检查红灯：phase速度应消失、freefill应消失、transform普通超车应恢复、状态应全0，同时扩大CTH和90m有见证关联保持。再核验1000随机状态的原NoA与safe_speed/cf_speed hexexact，并检验标签/排列/感知外不干扰。所有oracle使用固定Git S blob或已锁B源，避免后续安装改变生产文件后失效。
