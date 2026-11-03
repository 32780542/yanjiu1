"""Lossless per-profile archives; the original combined archive is immutable."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
BASE=Path(__file__).resolve().parent.parent
OLD=BASE/'formation_demo_long/evidence_reviewed.tar.gz'
OUT=BASE/'formation_demo_long_split'
EXPECTED='6fefa8466985a9bfdce30652f8c6bb163d6f3018882fe22d994000cfb453e766'
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(OLD.read_bytes())==EXPECTED
assert not OUT.exists();OUT.mkdir()
tags=['E2400','J22400'];mapping={};outputs=[]
with tarfile.open(OLD) as source:
    original=source.extractfile('manifest.json').read();manifest=json.loads(original)
    for name in manifest:
        scoped=None
        for tag in tags:
            if any(name.startswith(prefix+tag+'/') for prefix in ['raw/','frozen_runtime/','reviewed/','reviewed/sources_original/']):scoped=tag
            if name.startswith('operations/') and tag+'-demo-' in name:scoped=tag
        mapping[name]=[scoped] if scoped else tags[:]
    rawmap=(json.dumps(dict(original_archive_sha256=EXPECTED,members=mapping),indent=2)+'\n').encode()
    for tag in tags:
        contents={n:source.extractfile(n).read() for n in manifest if tag in mapping[n]}
        contents['original_combined_manifest.json']=original
        contents['member_mapping.json']=rawmap
        packed={n:dict(bytes=len(raw),sha256=sha(raw)) for n,raw in contents.items()}
        archive=OUT/(tag+'_complete_evidence.tar.gz')
        with tarfile.open(archive,'w:gz',compresslevel=9) as target:
            for n,raw in [('manifest.json',(json.dumps(packed,indent=2)+'\n').encode()),*contents.items()]:
                info=tarfile.TarInfo(n);info.size=len(raw);target.addfile(info,io.BytesIO(raw))
        assert archive.stat().st_size<20_000_000
        with tarfile.open(archive) as target:
            audit=json.loads(target.extractfile('manifest.json').read());assert audit==packed
            for n,m in audit.items():
                raw=target.extractfile(n).read();assert len(raw)==m['bytes'] and sha(raw)==m['sha256']
        outputs.append(dict(profile=tag,archive=archive.name,bytes=archive.stat().st_size,sha256=sha(archive.read_bytes()),members_including_manifest=len(packed)+1,all_member_hashes_verified=True))
(OUT/'member_mapping.json').write_bytes(rawmap)
assert sha(OLD.read_bytes())==EXPECTED
(OUT/'verification.json').write_text(json.dumps(dict(original_combined_sha256_unchanged=EXPECTED,lossless_all_original_members_covered=set(mapping)==set(manifest),profile_archives=outputs),indent=2)+'\n',encoding='utf-8')
(OUT/'README.md').write_text('# 原长下游证据按profile无损分包\n\n原26.9MB combined封包保持本地原样，SHA不变。E2400/J22400各包保留本profile完整raw positions/events/diagnostic、source/input、图表及共用工具/说明；共用材料在两包重复。`member_mapping.json`列原combined每个成员到新profile映射；各包自含新manifest、原combined manifest和mapping，逐成员SHA复核。两包合起来覆盖原manifest全部成员，未剪裁轨迹。\n\n'+ '\n'.join(f'- {r["archive"]}: {r["bytes"]:,} bytes，SHA256 `{r["sha256"]}`。' for r in outputs)+'\n',encoding='utf-8')
print(json.dumps(outputs))
