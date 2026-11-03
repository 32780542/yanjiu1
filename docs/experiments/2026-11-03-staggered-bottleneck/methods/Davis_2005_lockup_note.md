# Davis 2005：提前跨道协作也会出现lock-up

原始来源：L. C. Davis, *Effect of adaptive cruise control systems on mixed traffic flow near an on-ramp*, 2005作者稿，arXiv:physics/0506147。[作者稿PDF，定位第10页](https://arxiv.org/pdf/physics/0506147#page=10)，正文页码9，§4 “Cooperative merging”，式(29)后的末段、§5之前。这里页码及措辞均指该2005稿，不混用后来期刊版的页码或数值。

原文简短摘录（6个英文词）：

> Occasionally simulations revealed a lock-up phenomenon

该段报告：匝道车在合流段末端停滞，一辆主道ACC车也停在其后。作者在仿真中于ACC车速降至1–5m/s时设 `α=0`，撤销该提前合作项，从而避免此lock-up。同页式(27)之前明确，跨道参考是另一车道的**最近紧前车**；不是接收窗口内最远的候选头车。[Davis 2005作者稿，正文p.9](https://arxiv.org/pdf/physics/0506147#page=10)

可用于本项目报告的准确表述：提前跨道接收控制本身也可能造成相互等待；文献中的流量收益包含明确的异常处理，不能把“存在虚拟前驱”当成无需例外的畅通保证。该文情景、纵向模型、合流规则与本项目不同，这一段不证明本项目旧helper/receiving链与其lock-up具有完全相同的因果机制。

本note只提供原文证据和适用边界，没有给E/H增加低速门槛、撤销规则或虚拟CF，也不把论文参数作为本项目已验证参数。
