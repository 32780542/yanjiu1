"""Algebra and finite code witnesses; no traffic simulation, no source edits.

Run from any directory:
  python -B <absolute-path>/theory_check.py
Output defaults to theory_check.json next to this script.
"""
from __future__ import annotations

import argparse
import cmath
from dataclasses import replace
from fractions import Fraction as F
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import subprocess

sys.dont_write_bytecode = True

EXPECTED = {
    "S": ("variants/phase5g_pure_formation/noa/native_rules.py",
          "8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f"),
    "V1": ("tmp/staggered_bottleneck/candidates/midflow_projected_predecessor_v1/native_rules.py",
           "517d169ff012950e288c20a9fca9225db20bae6ffcc1a6f3aca43c05c8790c7d"),
    "executor": ("variants/phase5g_pure_formation/experiments/native_sumo.py",
                 "bc22273fa224206e03dd896fb7b386a5d28ce3526fddebfa6bf7d7c93caaa1d1"),
}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def roots2(a, b, c):
    disc = cmath.sqrt(b * b - 4 * a * c)
    return [(-b + disc) / (2 * a), (-b - disc) / (2 * a)]


def encode_complex(z):
    return {"real": z.real, "imag": z.imag, "abs": abs(z)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--output", type=Path, default=Path(__file__).with_suffix(".json"))
    args = parser.parse_args()
    provenance = {}
    for name, (relative, expected) in EXPECTED.items():
        path = args.root / relative
        source = (subprocess.check_output(["git", "show", "1aa86344af2a269053cd4fcda9d58168697daf17:" + relative], cwd=args.root)
                  if name == "S" else path.read_bytes())
        actual = hashlib.sha256(source).hexdigest()
        if actual != expected:
            raise RuntimeError(f"Frozen source mismatch for {name}: {actual}")
        provenance[name] = {"path": ("git:1aa86344af2a269053cd4fcda9d58168697daf17:" + relative
                                    if name == "S" else str(path.resolve())), "sha256": actual}
    r = load_module("theory_frozen_v1", args.root / EXPECTED["V1"][0])

    # Exact rational arithmetic for all conditions, then floats for diagnostics.
    dt, response, gain = F(1, 10), F(1, 2), F(3, 10)
    headway = F(245, 288)
    alpha = dt / response
    a = 1 - alpha * (1 + gain * headway)
    q = dt * alpha * gain
    trace = 1 + a - q
    continuous_margin = 2 * headway + gain * headway**2 - 2 * response
    discrete_margin = continuous_margin + dt * gain * headway
    A = 2 * ((1 - a)**2 - alpha**2 - q * (1 + a + alpha))
    B = 4 * a
    assert A == 2 * alpha**2 * gain * discrete_margin
    jury = [q, 2 + 2 * a - q, 1 - a]
    assert all(value > 0 for value in jury)
    assert continuous_margin > 0 and A >= 0 and A + 2 * B >= 0
    poles_c = roots2(float(response), float(1 + gain * headway), float(gain))
    poles_d = roots2(1, -float(trace), float(a))

    # Checks of the polynomial identity on the unit circle. These are not proofs.
    maximum_identity_error = 0.0
    maximum_discrete_gain = (1.0, 0.0)
    for index in range(1, 20001):
        theta = math.pi * index / 20000
        z = cmath.exp(1j * theta)
        numerator = float(alpha + q) * z - float(alpha)
        denominator = z*z - float(trace) * z + float(a)
        u = 1 - math.cos(theta)
        difference = abs(denominator)**2 - abs(numerator)**2
        polynomial = float(A) * u + float(B) * u*u
        maximum_identity_error = max(maximum_identity_error, abs(difference - polynomial))
        ratio = abs(numerator / denominator)
        if ratio > maximum_discrete_gain[0]:
            maximum_discrete_gain = (ratio, theta)
    assert maximum_identity_error < 1e-12
    assert maximum_discrete_gain[0] <= 1.0 + 1e-12

    def car(track, x, lane, speed):
        return r.Vehicle(track, x, (lane + .5) * r.LANE_WIDTH, speed, lane)

    ego = car(0, 700., 1, 20.)
    d0 = r.LENGTH + r.STANDSTILL
    # Actual CTH=20.20, projected CTH=20.19. The lane1/2 phase edge adds 0.015.
    actual_speed = 21.0 - r.POSITION_GAIN * (30. - d0 - r.HEADWAY * ego.speed)
    merging_speed = 20.95 - r.POSITION_GAIN * (15.5 - d0 - r.HEADWAY * ego.speed)
    actual = car(1, 730., 1, actual_speed)
    merging = car(2, 715.5, 2, merging_speed)
    rows = (actual, merging)
    actual_cth = r._front_following(ego, rows)[0]
    projected = replace(merging, lane=1, y=1.5*r.LANE_WIDTH, vy=0.)
    projected_cth = r._front_following(ego, (*rows, projected))[0]
    follow = r._following(ego, rows, 2, 640., (640., 1000.))
    command, memory = r.decide(ego, rows, r.Memory(joining=True), "transform")
    safety_cap = r.safe_speed(ego, rows)
    assert projected_cth < actual_cth < command.speed < safety_cap
    assert math.isclose(actual_cth, 20.20, abs_tol=1e-12)
    assert math.isclose(projected_cth, 20.19, abs_tol=1e-12)
    assert math.isclose(command.speed, 20.205, abs_tol=1e-12)
    assert 0 <= (command.speed - ego.speed) / float(dt) <= 5.0
    assert command.reference == merging.track and command.lane is None

    # Finite observation and label witnesses, not a universal testing proof.
    invisible = car(77, 901., 1, 0.)  # >200m ahead: outside the observation cut.
    altered, altered_memory = r.decide(
        ego, (*rows, invisible), r.Memory(joining=True), "transform")
    assert altered == command and altered_memory == memory
    labels = {0: 400, 1: 913, 2: 12}
    labeled = lambda vehicle: replace(vehicle, track=labels[vehicle.track])
    changed, changed_memory = r.decide(
        labeled(ego), tuple(labeled(c) for c in reversed(rows)),
        r.Memory(joining=True), "transform")
    assert changed.speed == command.speed and changed.lane == command.lane
    assert changed.target_x == command.target_x and changed.reason == command.reason
    assert changed.reference == labels[command.reference]
    assert changed_memory == memory

    report = {
        "scope": "algebra plus finite pure-function witnesses; no SUMO/traffic simulation",
        "source_provenance": provenance,
        "parameters": {"dt_s": float(dt), "T_s": float(response), "k_per_s": float(gain),
                       "H_s": float(headway), "alpha": float(alpha)},
        "continuous": {"stable": all(z.real < 0 for z in poles_c),
                       "poles": [encode_complex(z) for z in poles_c],
                       "string_margin_2H_plus_kH2_minus_2T": float(continuous_margin),
                       "H_threshold_s": (-1 + math.sqrt(1 + 2*float(gain*response))) / float(gain)},
        "semi_implicit_discrete_conditional": {
            "assumptions": "fixed observed predecessor; commanded speed applied exactly next step; no clipping or switching",
            "a": float(a), "q": float(q), "trace": float(trace),
            "poles": [encode_complex(z) for z in poles_d],
            "jury_margins": [float(value) for value in jury],
            "unit_circle_difference_A": float(A), "unit_circle_difference_B": float(B),
            "string_margin": float(discrete_margin),
            "H_threshold_s_for_nonnegative_a": (
                -(2+float(dt*gain)) + math.sqrt(float((2+dt*gain)**2 + 8*gain*response))
            ) / float(2*gain),
            "frequency_grid_points": 20001,
            "max_gain_including_DC": maximum_discrete_gain[0],
            "max_polynomial_identity_absolute_error": maximum_identity_error,
        },
        "actual_cth_not_final_upper_bound_witness": {
            "ego": {"x": ego.x, "speed": ego.speed, "lane": ego.lane},
            "real_front": {"x": actual.x, "speed": actual.speed, "lane": actual.lane},
            "merging": {"x": merging.x, "speed": merging.speed, "lane": merging.lane},
            "raw_actual_cth_mps": actual_cth, "raw_projected_cth_mps": projected_cth,
            "following_after_phase_mps": follow[0], "decide_speed_mps": command.speed,
            "physical_safe_cap_mps": safety_cap,
            "implied_ego_acceleration_mps2": (command.speed-ego.speed)/float(dt),
            "no_requested_lane_change": command.lane is None,
            "reference_is_projected_vehicle": command.reference == merging.track,
        },
        "finite_contract_witnesses": {
            "invisible_added_vehicle_does_not_change_action": True,
            "bijective_labels_and_reversed_observation_order_preserve_physical_action": True,
        },
        "not_established": ["full S/V string stability", "collision-free invariance", "global convergence",
                            "SUMO executed speed always equals request", "traffic performance improvement"],
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()),
                      "continuous_margin": float(continuous_margin),
                      "discrete_margin": float(discrete_margin),
                      "discrete_poles_abs": [abs(z) for z in poles_d],
                      "cth_counterexample_mps": [actual_cth, projected_cth, command.speed],
                      "all_assertions_passed": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
