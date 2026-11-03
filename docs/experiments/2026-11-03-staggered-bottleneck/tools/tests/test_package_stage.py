"""Publication extraction must remain bounded and byte-exact."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))


class StagePackageContracts(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE / "package_stage.py").is_file(), "stage packaging implementation is missing")
        import package_stage
        self.tool = package_stage
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, name="data/file.txt", payload=b"evidence", declared=None, original=None):
        expected = payload if declared is None else declared
        index = dict(format="staggered-stage-v1", members={name: dict(bytes=len(expected),
            sha256=hashlib.sha256(expected).hexdigest(), original_path=str(original) if original else None)})
        path = self.root / "bundle.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for member, data in (("index.json", json.dumps(index).encode()), (name, payload)):
                info = tarfile.TarInfo(member)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return path

    def test_member_paths_cannot_escape_or_use_windows_drive_paths(self):
        for name in ("../outside", "/outside", "C:/outside", "data/../../outside", "data\\outside"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.tool.safe_member(name)

    def test_valid_archive_extracts_and_matches_original_bytes(self):
        original = self.root / "original.txt"
        original.write_bytes(b"evidence")
        archive = self.archive(original=original)
        self.tool.extract_checked(archive, self.root / "extracted", check_originals=True)
        self.assertEqual((self.root / "extracted/data/file.txt").read_bytes(), original.read_bytes())

    def test_hash_corruption_is_rejected(self):
        archive = self.archive(payload=b"altered!", declared=b"evidence")
        with self.assertRaisesRegex(ValueError, "hash|size"):
            self.tool.extract_checked(archive, self.root / "extracted")

    def test_original_byte_mismatch_is_rejected(self):
        original = self.root / "original.txt"
        original.write_bytes(b"different")
        archive = self.archive(original=original)
        with self.assertRaisesRegex(ValueError, "original"):
            self.tool.extract_checked(archive, self.root / "extracted", check_originals=True)


if __name__ == "__main__":
    unittest.main()
