# ENP：E上的形成消融

仅用于因果诊断，不作为生产候选。父源码SHA：`04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274`。

- `phase_speed = max(-2.0, min(2.0, POSITION_GAIN * error))` → `phase_speed = 0.0  # diagnostic ENP: disable cross-lane head speed correction`

保留NOA、实际前车CTH、安全、必要合流、原0/1及未关闭的组织行为。ENP保留用于匹配/补位的相位坐标，仅禁止队首速度修正。1000个影子状态NOA精确相同、同物理帧0/1相同；不能据此宣称交通效果或形成几何。
