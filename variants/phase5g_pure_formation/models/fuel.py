"""SUMO 1.27.1 HBEFA3/PC_G_EU4 的瞬时燃油估计，单位 mg/s。

系数及断油条件来自 eclipse-sumo/sumo 的 v1_27_1：
src/utils/emissions/HelpersHBEFA3.cpp、HelpersHBEFA3.h、PollutantsInterface.cpp。
统一采用默认1500kg、默认迎风面积、平路和发动机开启；与本机官方工具对照。
"""

import math


def coasting_acceleration(speed_mps):
    """发动机制动断油阈值；对应官方默认能量参数。"""
    minimum = 10/3.6
    speed = max(speed_mps, minimum)
    area = 1.8*1.5*math.pi/4
    slope = area/1500*-9.05337017 - .00017774
    threshold = min(0., slope*speed + .00001066*1500 - .38347107 - 20*slope)
    return threshold * min(1., speed_mps/minimum)


def fuel_rate_mg_s(speed_mps, acceleration_mps2):
    """实际速度、实际纵向加速度输入；返回质量流率，累计时需乘 dt。"""
    v, a = speed_mps, acceleration_mps2
    if v > .5 and a < coasting_acceleration(v):
        return 0.
    return max((3014 + 299.3*a*v - 149*v + 9.014*v*v)/3.6, 0.)
