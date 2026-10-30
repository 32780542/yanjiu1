"""Load the published state-only baseline without Git or extracting archive files."""
import hashlib
from pathlib import Path
import sys
import tarfile
import types


ARCHIVE = (Path(__file__).resolve().parents[3]
           / "docs/experiments/2026-10-29-local-formation-state/evidence.tar.gz")
MEMBER = "current_source/noa/native_rules.py"
SOURCE_SHA256 = "ac1c5aba082130718c81a23eb2c7bc9708caa8dae6b138baea951d07e735ee7d"


def load_state_enabled_base(label):
    """Give each historical test an independent, hash-verified module namespace."""
    with tarfile.open(ARCHIVE, "r:gz") as archive:
        with archive.extractfile(MEMBER) as stream:
            source = stream.read()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise AssertionError("Published state-enabled baseline source hash mismatch")
    name = "archived_state_enabled_base_" + label
    module = types.ModuleType(name)
    module.__file__ = str(ARCHIVE) + ":" + MEMBER
    sys.modules[name] = module
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module
