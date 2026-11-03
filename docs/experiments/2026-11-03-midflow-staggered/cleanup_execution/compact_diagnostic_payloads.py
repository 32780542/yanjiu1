"""Remove exact local payload duplicates after verifying both published archives."""
from pathlib import Path
import hashlib
import json
import subprocess
import tarfile


STAGE = Path(__file__).resolve().parents[1]
ROOT = STAGE.parents[2]
DIAG = STAGE / 'diagnosis'
OUT = Path(__file__).resolve().parent / 'diagnostic_payload_cleanup'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    assert not OUT.exists(), 'Preserve previous attempts; inspect before any retry.'
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0'))
    targets, archives = [], []
    for stem in ('closed_diagnostic_tables', 'final91_diagnostic_tables'):
        index_path = DIAG / (stem + '_index.json')
        index = json.loads(index_path.read_text(encoding='utf-8'))
        archive_path = DIAG / (stem + '.tar.gz')
        assert digest(archive_path) == index['archive_sha256']
        assert archive_path.relative_to(ROOT).as_posix() in tracked
        with tarfile.open(archive_path, 'r:gz') as archive:
            members = archive.getmembers()
            assert [m.name for m in members] == [r['path'] for r in index['members']]
            for member, record in zip(members, index['members']):
                path = (DIAG / record['path']).resolve()
                assert path.is_relative_to(DIAG.resolve()) and not Path(record['path']).is_absolute()
                first = path.relative_to(DIAG.resolve()).parts[0]
                assert first.startswith('raw_') or 'fill_scores_v1' in first
                assert path.relative_to(ROOT).as_posix() not in tracked
                assert member.isfile() and member.size == path.stat().st_size == record['bytes']
                assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == record['sha256']
                assert digest(path) == record['sha256']
                targets.append({'path': str(path), 'bytes': record['bytes'], 'sha256': record['sha256']})
        archives.append({'archive': archive_path.name, 'sha256': index['archive_sha256'],
                         'index_sha256': digest(index_path), 'members': len(index['members'])})
    assert len({r['path'].casefold() for r in targets}) == len(targets)
    OUT.mkdir()
    plan = {'scope': 'untracked duplicates of exact archived diagnostic members only',
            'archives': archives, 'targets': targets, 'script_sha256': digest(Path(__file__))}
    (OUT / 'verified_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for record in targets:
        path = Path(record['path'])
        assert digest(path) == record['sha256']
        path.unlink()
    assert all(not Path(r['path']).exists() for r in targets)
    result = {'status': 'complete', 'files_removed': len(targets),
              'bytes_released': sum(r['bytes'] for r in targets),
              'archives_verified_and_retained': archives, 'recursive_delete': False,
              'traffic_raw_or_geometry_removed': False, 'restore': 'tar -xzf ARCHIVE inside diagnosis'}
    (OUT / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
