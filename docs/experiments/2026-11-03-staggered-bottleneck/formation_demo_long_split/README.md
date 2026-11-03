# 原长下游证据按profile无损分包

原26.9MB combined封包保持本地原样，SHA不变。E2400/J22400各包保留本profile完整raw positions/events/diagnostic、source/input、图表及共用工具/说明；共用材料在两包重复。`member_mapping.json`列原combined每个成员到新profile映射；各包自含新manifest、原combined manifest和mapping，逐成员SHA复核。两包合起来覆盖原manifest全部成员，未剪裁轨迹。

- E2400_complete_evidence.tar.gz: 13,484,625 bytes，SHA256 `a8878d61cd3434caab38052fa0e2342337f75e37bbbcad30a83d5ee55fd443d0`。
- J22400_complete_evidence.tar.gz: 13,624,107 bytes，SHA256 `b179f267742fe0890ddc5e3068fd3c4fbf096d0bc3363c0c7161f3d151dce2b8`。
