"""Archive closed diagnostic tables without changing or deleting their originals."""
from pathlib import Path
import hashlib
import json
import tarfile


ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'closed_diagnostic_tables.tar.gz'
INDEX = ROOT / 'closed_diagnostic_tables_index.json'


def sha256(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def main():
    assert not ARCHIVE.exists() and not INDEX.exists(), 'Use a new output for any retry.'
    folders = sorted(p for p in ROOT.iterdir() if p.is_dir() and
                     (p.name.startswith('raw_') or 'fill_scores_v1' in p.name))
    files = sorted(p for folder in folders for p in folder.rglob('*') if p.is_file())
    records = [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                'sha256': sha256(p)} for p in files]
    with tarfile.open(ARCHIVE, 'w:gz', compresslevel=6) as archive:
        for path in files:
            archive.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
    with tarfile.open(ARCHIVE, 'r:gz') as archive:
        members = archive.getmembers()
        assert [m.name for m in members] == [r['path'] for r in records]
        for member, record, path in zip(members, records, files):
            assert member.isfile() and member.size == record['bytes']
            assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == record['sha256']
            assert sha256(path) == record['sha256'], 'Original changed while packing.'
    output = {'status': 'verified', 'originals_modified': False, 'originals_deleted': False,
              'scope': [p.name for p in folders], 'members': records,
              'original_bytes': sum(r['bytes'] for r in records),
              'archive_bytes': ARCHIVE.stat().st_size, 'archive_sha256': sha256(ARCHIVE),
              'restore_directory': 'docs/experiments/2026-11-03-midflow-staggered/diagnosis'}
    INDEX.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in output.items() if k not in ('scope', 'members')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
