# C5 mode别名记录

C5R/G四份冻结源的`_decide`在处理`noa`后，没有再用`mode`区分formation和transform。因此两种模式都会启用主动虚拟接收及未知道路的lane2跟随，不能用这两个模式做形成/变换机制消融。

`test_forward_C6.py`已在冻结C5R复现两个反例：

- 1道本车x880、2道车x895、真实1道前车x930，已知道路时，formation与transform都把x895车作为虚拟前驱。
- 未知道路，2道本车x880、最近真实2道前车x910正在2→1时，formation与transform都会发起向1跟随。

C5G与R仅差半D空位界，具有相同mode别名问题。原件和既有结果保留；这不改变已经运行的C5 **transform**控制器实际做过什么，也不使其相对NOA的实测自动无效，但C5不能支持formation/transform两种机制有区别的消融结论。C6恢复明确mode语义后再做该项消融。
