# JT2：物理邻接与仅速度伸缩增量

固定旧JT SHA `443e082742d1400ad03b4381e91cdace35cde522c48b6f11efd375ff89af287e`，只把_following邻道枚举改为 `lane<3`。相对J2仍只差对称平均速度下的phase伸缩因子，其余完全相同；不改巡航30/15自由fill模板。

新源441行，SHA `b415daca538202594a1b12fc768ed3a60a9c30a2f37221625ef1bf3be331df48`。新4+原12联合16项及101子测试通过；JT低速body平衡、head自由回CRUISE和最终硬安全均保留。旧JT、E、生产、原核心tests保持。

完整数学、Meere/Zheng引用、无V2V证明边界与红绿记录见[共同方法记录](../../methods/J_JT_local_coupling.md)。
