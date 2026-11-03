# 固定LP0可作为M关闭纵向相位的严格控制等价消融

**结论：可以复用同输入、同非控制源码/物理参数的既有LP0结果作为M关闭纵向phase_speed的消融，无需重复仿真。** 这不是M与LP0本身等价，而是M把phase_speed置0之后等价。也不能把它称为MN关闭相位：MN另有N释放，LP0没有。

固定M SHA `a286110cf2e14904152b63c9a66f960496f5f7f04ab0097b8d7ed00353db4762`；固定LP0（phase_off_L）SHA `64a134fee75ae628779b81e497fca1de6b095a2f1828493c573ee2dacc455eb4`。只在内存把M原phase_speed限幅赋值改为LP0同一 `phase_speed=0.0`，得到虚拟M0 SHA `7957ce027bf8a2a305ff2a79cfe5cfc743d95e7cb59aa63a547f79308cee3356`，没有写新候选、覆盖LP0或跑仿真。

## AST与数据流证明

[核验脚本](verify_LP0_M_phase_zero.py)先验证两个原源hash，并硬断言虚拟M0与LP0逐字差异只有_following内一条error累加右式：

```text
LP0: error += difference / n
M0:  error += (difference + (peer.speed−ego.speed)/POSITION_GAIN) / n
两者后续都：phase_speed = 0.0
```

1. 相位归零后，整个_following没有任何显式`error` Load。`error +=`确有隐含自读，但只写回这个死变量，结果不控制分支、不返回、不写Memory。
2. 删除两者相同的初始error赋值及各自死error累加后，**整模块AST完全相同**；不只比较某一个返回数字。所有类、参数、默认范围50、L witness、CTH、fill、安全与_decide都相同。
3. nearest/order及linked更新均不读取error，且在累加前按相同实际邻边完成。故相位归零仍保留同样关系flags，不会把“关闭速度修正”误写成“删除邻接图”。
4. body使用相同实际front target/reference及相同0相位增量；head使用相同自身x+0/.3、原巡航_request。其后_decide读到的速度/目标/ref/关系位相同，自身Memory更新和执行优先级也相同。
5. 有效Vehicle速度0至33.3、当前边≤50m、POSITION_GAIN=.3非零且n≥1。M0多算的相对速度算术是有限纯浮点操作，不会产生额外写入或异常。证明范围为项目有效物理状态的控制输出/Memory；计算次数及墙钟无需相同。

## 6000组三模式精确比较

使用优化前已保存的有效有限oracle输入，SHA `a24adc6bee09319fd1d71eb05c468be76bed54b41d9dd8e55caa43731fbe91f6`。前6000组包含406个原100/180/250s实测ego观测及固定随机的横移、边界、前后车、同x和不同自身Memory。

- 每组noa/formation/transform全部运行：**18000个完整Command及Memory按float.hex精确相同**，包括目标、reference、reason、lane、状态0/1和自身gap。
- 6000个safe_speed额外hex精确相同。
- 其中10006个命令的formation_state=1，比较不局限于没有关系的孤立车辆。
- M、LP0、L和生产源运行前后字节不变。

operation `20261103T064115772840Z_LP0-M-phase-zero-AST-and-6000-equivalence_9c111b61`，exit0，5.954秒。详细身份/AST/dataflow/计数保存在[LP0_M_phase_zero_equivalence.json](LP0_M_phase_zero_equivalence.json)。

复用时仍按实际同arrival tape、道路、seed、物理和非控制源逐项匹配，不能以该控制等价结论跨输入或改变LP0原source记录。现有LP0保留其真实L-phase0源码身份，可在报告中注明经过此证明等价M-phase0；不重标旧hash或重写旧protocol。
