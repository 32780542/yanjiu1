"""核对固定队形调距方程的特征值。"""
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "variants/phase5g_pure_formation"))
from noa.native_rules import CRUISE, HEADWAY, POSITION_GAIN, SPEED_RELAXATION, desired_spacing


def shape_spectrum(layers, step=.1):
    ranks = np.array([rank + (lane % 2) / 2 for rank in range(layers) for lane in range(3)])
    positions = -ranks * desired_spacing(CRUISE)
    distance = positions[None, :] - positions[:, None]
    weights = ((distance >= -100.) & (distance <= 200.)).astype(float)
    weights /= weights.sum(axis=1, keepdims=True)
    identity = np.eye(len(ranks))
    gain = SPEED_RELAXATION * POSITION_GAIN
    position_feedback = -gain * (identity - weights)
    speed_feedback = np.diag(1 - SPEED_RELAXATION + gain * HEADWAY * (weights @ ranks - ranks))
    update = np.block([[identity + step * position_feedback, step * speed_feedback],
                       [position_feedback, speed_feedback]])
    roots = np.linalg.eigvals(update)
    translation = abs(roots - 1) < 1e-8
    return translation.sum(), max(abs(roots[~translation]))


if __name__ == "__main__":
    for layers in (2, 3, 4):
        translations, radius = shape_spectrum(layers)
        print(f"{layers} 层，平移根 {translations} 个，其他根最大模 {radius:.5f}")
