"""Verify installed bytes, existing test evidence, final data and document links."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re


ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / 'docs/experiments/2026-11-03-midflow-staggered'
VARIANT = ROOT / 'variants/phase5g_pure_formation'
RULE_SHA = '2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def table(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def main(destination):
    rule = VARIANT / 'noa/native_rules.py'
    assert sha256(rule) == RULE_SHA and len(rule.read_text(encoding='utf-8').splitlines()) == 423
    installed = read(STAGE / 'implementation/installed_D1_migrated_core.json')
    assert installed['returncode'] == 0 and installed['tests_on_disk']
    assert not installed['module_injection']
    for path, digest in installed['source_and_test_hashes'].items():
        assert sha256(VARIANT / path) == digest, path
    entry = STAGE / 'implementation/native_entry'
    operations = sorted(entry.glob('*_result.json'))
    operations = [p for p in operations if p.name != 'smoke_result.json']
    assert len(operations) == 3
    for path in operations:
        result = read(path)
        assert result['returncode'] == 0 and result['status'] == 'completed'
    smoke = read(entry / 'smoke_result.json')
    assert smoke['safe'] and smoke['all_completed'] and smoke['requested'] == smoke['completed'] == 30
    final = STAGE / 'diagnosis/final91_independent_v1'
    verification = read(final / 'verification.json')
    assert verification['cases_n'] == verification['eligible_cases_n'] == 90
    assert verification['primary_pairs_n'] == verification['secondary_pairs_n'] == 30
    assert verification['primary_road_DID_n'] == verification['secondary_road_DID_n'] == 15
    assert verification['raw_reconstructed'] and verification['raw_gate_endpoint_checks'] == 978696
    for path, digest in verification['nonrule_sources_sha256'].items():
        assert sha256(VARIANT / path) == digest, path
    means = table(final / 'flow_means.csv')
    assert len(means) == 12 and {int(r['flow']) for r in means} == {1500, 1750, 2000}
    for row in means:
        assert int(row['eligible_n']) == int(row['pairs_n']) == int(row['system_faster_n']) == 5
    did = table(final / 'road_did_flow_means.csv')
    assert [int(r['extra_lane_drop_saving_n']) for r in did] == [4, 4, 5, 5, 5, 4]
    formation = table(STAGE / 'final91_all90/analysis/formation_per_case_from_result.csv')
    assert len(formation) == 90
    for row in formation:
        if row['method'] == 'NOA':
            assert all(float(row[k]) == 0 for k in ('participation_rate', 'mean_participants',
                                                   'peak_participants', 'episodes'))
            assert row['mean_episode_s'] == row['max_episode_s'] == ''
    docs = [ROOT / 'README.md', ROOT / 'docs/原生SUMO编队变换系统说明.md',
            STAGE / 'README.md', STAGE / '论文主线与贡献.md', STAGE / '方法贡献与论证结构.md']
    links = 0
    for path in docs:
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if target.startswith(('http:', 'https:', 'mailto:', '#')):
                continue
            local = re.sub(r':\d+$', '', target.split('#')[0])
            assert (path.parent / local).exists(), (path.name, target)
            links += 1
    result = {'status': 'verified', 'rule_sha256': RULE_SHA, 'rule_lines': 423,
              'installed_source_and_test_files': len(installed['source_and_test_hashes']),
              'existing_entry_operations': len(operations), 'smoke_completed': 30,
              'final_cases': 90, 'formation_result_cases': 90, 'local_document_links': links,
              'documents_sha256': {p.relative_to(ROOT).as_posix(): sha256(p) for p in docs}}
    assert not destination.exists(), 'Preserve old verification; use a new output for any retry.'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=STAGE / 'implementation/delivery_verification.json')
    main(parser.parse_args().output)
