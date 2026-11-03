"""Write a reviewable four-test patch; never edit the original test files."""
import ast
import difflib
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
paths = [REPO / "variants/phase5g_pure_formation/tests" / name
         for name in ("test_native_rules.py", "test_ending_pair_scope.py")]
patches, metadata = [], []
for path in paths:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(True)
    edits = []
    for node in ast.walk(ast.parse(original)):
        if not isinstance(node, ast.FunctionDef):
            continue
        old = "".join(lines[node.lineno - 1:node.end_lineno])
        new = None
        if node.name == "test_middle_front_car_makes_room_in_the_other_retained_lane":
            new = old.replace(node.name, "test_middle_car_has_no_assigned_helper_role_in_direct_gap_policy")
            new = new.replace("        self.assertEqual(self.command(ego, others).lane, 0)\n",
                              """        command, memory = self.r.decide(ego, others, self.r.Memory(), "transform")
        self.assertIsNone(command.lane)
        self.assertIsNone(memory.lane_target)
        self.assertNotIn(command.reason, ("make_room", "prepare_room", "open_gap"))
""")
        elif node.name == "test_a_helper_tracks_the_gap_while_the_rear_opens_space":
            new = old.replace(node.name, "test_submitted_own_lane_request_keeps_tracking_the_actual_gap")
            new = new.replace('        _, memory = self.r.decide(ego, rows, self.r.Memory(), "transform")\n',
                              "        memory = self.r.Memory(lane_target=0, joining=True)\n")
        elif node.name == "test_an_ending_lane_follower_does_not_get_a_virtual_merged_rank_at_640":
            start = old.index("        before = self.command(ego, others)\n")
            new = old[:start] + """        after_ego = replace(ego, x=641.0)
        shifted = [replace(c, x=c.x + 2.0) for c in others]
        before_follow = self.r._following(ego, others, 3, 640.0)
        after_follow = self.r._following(after_ego, shifted, 3, 640.0)
        self.assertEqual((before_follow[2], after_follow[2]), (1, 1))
        self.assertAlmostEqual(after_follow[1], before_follow[1] + 2.0)
        command, memory = self.r.decide(after_ego, shifted, self.r.Memory(), "transform")
        self.assertEqual(command.reason, "approach_gap")
        self.assertIsNone(command.lane)
        self.assertEqual(memory.gap, (4, 3))
        self.assertAlmostEqual(command.target_x, (shifted[2].x + shifted[3].x) / 2)
        self.assertLessEqual(command.speed, self.r.safe_speed(after_ego, shifted))
"""
        elif node.name == "test_separate_ending_unit_waits_using_its_actual_three_lane_phase":
            new = """def test_ending_unit_approaches_its_actual_gap_without_a_distant_head_wait():
    ego,front,middle=car(0,700,2),car(1,770,2),car(2,700,1)
    command,memory=r.decide(ego,[front,middle],r.Memory(),'transform',1000)
    assert command.reason=='approach_gap'
    assert command.lane is None
    assert memory.gap==(None,middle.track)
    assert command.target_x==715.0
    assert command.speed>r.CRUISE
"""
        if new is not None:
            assert new != old
            edits.append((node.lineno - 1, node.end_lineno, new, node.name))
    for start, end, new, _ in sorted(edits, reverse=True):
        lines[start:end] = new.splitlines(True)
    modified = "".join(lines)
    compile(modified, str(path), "exec")
    relative = path.relative_to(REPO).as_posix()
    patches.append("".join(difflib.unified_diff(original.splitlines(True), modified.splitlines(True),
                                               fromfile="a/" + relative, tofile="b/" + relative)))
    metadata.append(dict(path=relative, original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         modified_text_sha256=hashlib.sha256(modified.encode()).hexdigest(),
                         changed_tests=[entry[3] for entry in edits]))
assert sum(len(x["changed_tests"]) for x in metadata) == 4
(OUT / "test_migration.patch").write_text("".join(patches), encoding="utf-8", newline="\n")
(OUT / "test_migration_sources.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(patch=str(OUT / "test_migration.patch"), tests=4, original_tests_edited=False)))
