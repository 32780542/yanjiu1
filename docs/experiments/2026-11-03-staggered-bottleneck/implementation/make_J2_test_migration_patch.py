"""Generate J2's separate, formula-based core migration; never edit core tests."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

from run_core_with_rules import memory_test_patch


OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
TESTS = REPO / "variants/phase5g_pure_formation/tests"
E_PATCH = OUT / "test_migration.patch"
e_texts = memory_test_patch(E_PATCH, text_only=True)


def test(name, body):
    return f"    def {name}(self):\n" + "".join("        " + line + "\n" if line else "\n"
                                                     for line in body.strip().splitlines())


updates = {
    "test_native_rules.py": {
        "test_equal_distance_actual_heads_use_signed_geometry_not_track_order": test(
            "test_equal_phase_error_prefers_nearer_physical_peer_without_track_order", '''ego = self.car(0, 300.0, 0)
# The peers have equal |dx+15|=26, but physical distances are 41 and 11m.
others = [self.car(99, 259.0, 1), self.car(1, 311.0, 1)]
a = self.r._following(ego, others, 3)
changed = [replace(c, track=100-c.track) for c in reversed(others)]
self.assertEqual(a, self.r._following(ego, changed, 3))
self.assertAlmostEqual(a[1], ego.x + 2.0 / self.r.POSITION_GAIN)
self.assertAlmostEqual(a[0], self.r.CRUISE + 2.0 * self.r.SPEED_RELAXATION)
self.assertIsNone(a[2])'''),
        "test_retained_lane_head_does_not_follow_an_ending_car_behind": test(
            "test_retained_head_couples_to_actual_ending_peer_without_a_fake_front", '''ego = self.car(0, 700.0, 1)
peer = self.car(1, 670.0, 2)
a = self.command(ego, [peer])
# dx=-30 and phi(peer)-phi(ego)=-15; a three-lane edge clips at -2m/s.
self.assertIsNone(a.reference)
self.assertAlmostEqual(a.target_x, ego.x - 2.0 / self.r.POSITION_GAIN)
self.assertAlmostEqual(a.speed, self.r.CRUISE - 2.0 * self.r.SPEED_RELAXATION)
self.assertEqual(a.formation_state, 1)'''),
        "test_retained_lanes_restore_their_missing_cell_before_the_drop": None,
        "test_a_retained_head_adopts_the_two_lane_phase": test(
            "test_retained_head_keeps_the_physical_zero_fifteen_phase", '''ego = self.car(0, 700.0, 0)
reference = self.car(1, 700.0, 1)
command, _ = self.r.decide(ego, [reference], self.r.Memory(), "transform")
self.assertEqual((self.r._phase(0, 2), self.r._phase(1, 2)), (0.0, 15.0))
self.assertEqual((self.r._phase(0, 3), self.r._phase(1, 3)), (0.0, 15.0))
# Same-x outer->middle error is +15, not the former two-lane -15.
self.assertAlmostEqual(command.target_x, ego.x + 2.0 / self.r.POSITION_GAIN)
self.assertAlmostEqual(command.speed, self.r.CRUISE + 2.0 * self.r.SPEED_RELAXATION)
self.assertAlmostEqual(command.speed, self.r._request(ego, command.target_x, self.r.CRUISE))'''),
        "test_a_free_head_rejoins_cross_lane_alignment_after_lateral_completion": None,
    },
    "test_head_group_rules.py": {
        "test_real_lane_zero_head_c1_shares_phase_by_slowing": test(
            "test_real_lane_zero_head_c1_uses_fixed_phase_of_actual_a1", '''ego, (speed, target, reference) = self.command("C1")
peer = self.cars["A1"]
# The existing 11.537m separation needs +3.463m in fixed 0/15 geometry.
error = peer.x - ego.x + 15.0
self.assertIsNone(reference)
self.assertLess(abs(self.r.POSITION_GAIN * error), 2.0)
self.assertAlmostEqual(target, ego.x + error)
self.assertAlmostEqual(speed, r._request(ego, target, r.CRUISE))
self.assertGreater(speed, ego.speed)'''.replace("self.r.", "r.")),
        "test_real_lane_one_head_a1_shares_phase_by_accelerating": test(
            "test_real_lane_one_head_a1_uses_fixed_phase_of_actual_c1", '''ego, (speed, target, reference) = self.command("A1")
peer = self.cars["C1"]
error = peer.x - ego.x - 15.0
self.assertIsNone(reference)
self.assertLess(abs(r.POSITION_GAIN * error), 2.0)
self.assertAlmostEqual(target, ego.x + error)
self.assertAlmostEqual(speed, r._request(ego, target, r.CRUISE))
self.assertLess(speed, ego.speed)'''),
        "test_internal_b1_follows_only_its_physical_front_c1": test(
            "test_internal_b1_keeps_front_c1_and_couples_to_actual_body_a2", '''ego, (speed, target, reference) = self.command("B1")
front, peer = self.cars["C1"], self.cars["A2"]
distance = 5.5 + (30.0 - 5.5) / 28.8 * ego.speed
self.assertEqual(reference, front.track)
self.assertAlmostEqual(target, front.x - distance)
# The mutual B1/A2 body edge has e=+0.728852m, independently of CTH.
error = peer.x - ego.x + 15.0
phase_speed = max(-2.0, min(2.0, r.POSITION_GAIN * error))
expected = r._request(ego, front.x - distance, front.speed) + r.SPEED_RELAXATION * phase_speed
self.assertAlmostEqual(speed, max(0.0, min(r.MAX_SPEED, expected)))'''),
        "test_internal_a2_follows_only_its_physical_front_a1": test(
            "test_internal_a2_keeps_front_a1_and_couples_to_actual_body_b1", '''ego, (speed, target, reference) = self.command("A2")
front, peer = self.cars["A1"], self.cars["B1"]
distance = 5.5 + (30.0 - 5.5) / 28.8 * ego.speed
self.assertEqual(reference, front.track)
self.assertAlmostEqual(target, front.x - distance)
error = peer.x - ego.x - 15.0
phase_speed = max(-2.0, min(2.0, r.POSITION_GAIN * error))
expected = r._request(ego, front.x - distance, front.speed) + r.SPEED_RELAXATION * phase_speed
self.assertAlmostEqual(speed, max(0.0, min(r.MAX_SPEED, expected)))'''),
    },
    "test_common_pair.py": {
        "test_straight_and_outside_phase_geometry_matches_H": test(
            "test_raw_pair_uses_fixed_physical_phase_and_keeps_historical_H_distinct", '''for x,lanes,boundary in [(400.,3,None),(400.,3,640.),(1100.,2,640.)]:
    a,b=self.car(x,0),self.car(x+12,1,1)
    error,count=self.pair(a,b,lanes,boundary)
    historical=(b.x+H._physical_phase(b,lanes))-(a.x+H._physical_phase(a,lanes))
    self.assertEqual(count,lanes)
    self.assertAlmostEqual(error,b.x-a.x+15.0)
    # Frozen H still flips the retained two-lane phase; do not retarget H.
    self.assertAlmostEqual(error-historical,0.0 if lanes==3 else 30.0)'''),
        "test_mode_dispatch_uses_640_for_transform_and_1000_for_formation": None,
    },
    "test_ending_pair_scope.py": {
        "test_actual_ending_lane_keeps_three_lane_pair_geometry": '''def test_actual_ending_lane_keeps_three_lane_pair_geometry():
    a,b=car(0,700,2),car(1,700,1)
    forward,count=r._pair_error(a,b,3,640)
    backward,reverse_count=r._pair_error(b,a,2,640)
    assert count==reverse_count==3
    assert (r._phase(1,3),r._phase(2,3))==(15.0,0.0)
    # y=4.949999999999999 is continuously interpolated, not rounded to lane centre.
    physical_phase=r._physical_phase(b,3)-r._physical_phase(a,3)
    assert forward==physical_phase and backward==-physical_phase
    assert forward==-backward
''',
    },
    "test_formation_state.py": {
        "test_other_lane_body_is_not_a_mutually_selected_head": test(
            "test_actual_cross_lane_body_relation_counts_without_a_head_flag", '''ego = car(0, 90)
body, front = car(1, 100, 1), car(2, 145, 1)
self.assertEqual(rules._front_following(body, (ego, front))[2], front.track)
self.assertEqual(self.state(ego, (body, front)), 1)'''),
    },
}

patches, metadata = [], []
for name, mapping in updates.items():
    path = TESTS / name
    original = path.read_text(encoding="utf-8")
    source = e_texts.get(path.resolve(), original)
    lines = source.splitlines(True)
    edits = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef) or node.name not in mapping:
            continue
        old = "".join(lines[node.lineno - 1:node.end_lineno])
        new = mapping[node.name]
        if node.name == "test_retained_lanes_restore_their_missing_cell_before_the_drop":
            # q=x+phi: outer 785/(missing755)/725, middle 770/740/710.
            new = old.replace("((800.0, 1), (770.0, 1), (740.0, 1), (785.0, 0), (725.0, 0))",
                              "((770.0, 1), (740.0, 1), (710.0, 1), (785.0, 0), (725.0, 0))")
        elif node.name == "test_a_free_head_rejoins_cross_lane_alignment_after_lateral_completion":
            new = old.replace("self.assertGreater(command.speed, 28.8)",
                              "self.assertAlmostEqual(command.speed, self.r.CRUISE - 2.0 * self.r.SPEED_RELAXATION)")
            new = new.replace("self.assertGreater(command.target_x, ego.x)",
                              "self.assertAlmostEqual(command.target_x, ego.x - 2.0 / self.r.POSITION_GAIN)")
        elif node.name == "test_mode_dispatch_uses_640_for_transform_and_1000_for_formation":
            new = old.replace("self.assertAlmostEqual(formation.speed,28.95)",
                              "# Fixed raw error 20-15=5; common counts 3/2 retain different normalization.\n"
                              "        self.assertAlmostEqual(formation.speed,r.CRUISE+r.SPEED_RELAXATION*r.POSITION_GAIN*5/2)")
            new = new.replace("self.assertAlmostEqual(transform.speed,29.2)",
                              "self.assertAlmostEqual(transform.speed,r.CRUISE+r.SPEED_RELAXATION*r.POSITION_GAIN*5)")
        assert new and new != old, node.name
        edits.append((node.lineno - 1, node.end_lineno, new, node.name))
    assert len(edits) == len(mapping), name
    for start, end, new, _ in sorted(edits, reverse=True):
        lines[start:end] = new.splitlines(True)
    modified = "".join(lines)
    compile(modified, str(path), "exec")
    # Archived H/P test functions must stay byte-for-byte AST-identical.
    old_functions = {n.name: ast.dump(n) for n in ast.walk(ast.parse(original)) if isinstance(n, ast.FunctionDef)}
    new_functions = {n.name: ast.dump(n) for n in ast.walk(ast.parse(modified)) if isinstance(n, ast.FunctionDef)}
    frozen = [n for n in old_functions if n in (
        "test_all_actual_front_body_actions_remain_H_exact",
        "test_NOA_is_unchanged_even_with_compressed_rears",
        "test_control_and_memory_match_frozen_P_across_local_states")]
    assert all(old_functions[n] == new_functions[n] for n in frozen)
    relative = path.relative_to(REPO).as_posix()
    patches.append("".join(difflib.unified_diff(original.splitlines(True), modified.splitlines(True),
                                               fromfile="a/" + relative, tofile="b/" + relative)))
    metadata.append(dict(path=relative, original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         modified_text_sha256=hashlib.sha256(modified.encode()).hexdigest(),
                         j2_changed_tests=[e[3] for e in edits], archived_tests_unchanged=frozen))

assert sum(len(item["j2_changed_tests"]) for item in metadata) == 13
(OUT / "J2_test_migration.patch").write_text("".join(patches), encoding="utf-8", newline="\n")
(OUT / "J2_test_migration_sources.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(patch="J2_test_migration.patch", files=len(metadata), e_tests=4, j2_tests=13,
                      e_patch_sha256=hashlib.sha256(E_PATCH.read_bytes()).hexdigest(), original_tests_edited=False)))
