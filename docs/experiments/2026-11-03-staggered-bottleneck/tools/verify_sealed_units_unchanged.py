"""Final read-only SHA check of independently sealed geometry and long-run units."""
import hashlib,json
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
EXPECTED={
 'formation_demo/evidence_reviewed.tar.gz':'b97209b2612c27a4d177ea1595c929ad7b468adf3ae49488cc44e60987433585',
 'formation_demo_H/evidence_reviewed.tar.gz':'fc2162df5ca3d7ca38653ff9755f7aea8c4a9ab9bdb07a59c6a368f092ecf1c3',
 'formation_demo_J2/evidence_reviewed.tar.gz':'0fbf28680ff8ea19ba855e145e1f96fc6c4aaa609ff8cc7f506be643b7a71ff9',
 'formation_demo_JT2/evidence_reviewed.tar.gz':'da47465d6bdae379a1e66d99e68b295626a1f1f16b322f14f016eaa96a1b4a66',
 'formation_demo_long/evidence_reviewed.tar.gz':'6fefa8466985a9bfdce30652f8c6bb163d6f3018882fe22d994000cfb453e766',
 'formation_demo_long_split/E2400_complete_evidence.tar.gz':'a8878d61cd3434caab38052fa0e2342337f75e37bbbcad30a83d5ee55fd443d0',
 'formation_demo_long_split/J22400_complete_evidence.tar.gz':'b179f267742fe0890ddc5e3068fd3c4fbf096d0bc3363c0c7161f3d151dce2b8',
 'formation_demo_L_long/evidence_reviewed.tar.gz':'164228f63cb5846d6049cefe15ce9d4186461345607950d8be399ab1e4dd5df1',
 'formation_demo_M_long/evidence_reviewed.tar.gz':'0b907ff3bfe1abb715bc0c31b44db4294fe2882b2a4466865c0afb8da0a3b5ee',
 'formation_demo_N_long/evidence_reviewed.tar.gz':'d9893a28b44f4ccbdc55a7325b79034d8e61d51f1c2cee0f12bfceed521c1a9c',
 'formation_demo_Q_long/evidence_reviewed.tar.gz':'614427ccf271edd31d13de6d8eb7c2192c482d63a6e48d2209190c9858bcf783',
 'formation_demo_LP0_long/evidence_reviewed.tar.gz':'e512b30f5b6abeba53e01b76caf6f411fb930876e9469dde213ee8868d0d7f41',
 'formation_demo_LT_long/evidence_reviewed.tar.gz':'c7a5bbff10a3ddde2b3ecf514c0a2f510bb6af10bf71e34236ede8b59105aa59',
 'formation_demo_S_long/evidence_reviewed.tar.gz':'463b214f1615f15a485c5d97fa44c92380439e967b0cb2ecf4d848f10eacd40b',
 'long_window_NOA_S1800/evidence_profiles/NoA_four_cases_evidence.tar.gz':'877c3be2be615e0545989c056d882bbe3540078303b07a3ce6ae0309f9e3bcad',
 'long_window_NOA_S1800/evidence_profiles/S_four_cases_evidence.tar.gz':'2ffdefbb9b923575791f54a3f57bd185ab0091458ad1a0a583b8bbca5f376e1e',
}
records=[]
for relative,expected in EXPECTED.items():
    p=BASE/relative
    with p.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
    assert actual==expected,relative
    records.append(dict(path=relative,sha256=actual,bytes=p.stat().st_size,under20MB=p.stat().st_size<20_000_000))
result=dict(archives_checked=len(records),all_unchanged=True,only_original_combined_long_local_over20MB=[r['path'] for r in records if not r['under20MB']],archives=records)
(BASE/'sealed_units_final_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='archives'}))
