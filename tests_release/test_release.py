"""Release failures are caught before an archive is published."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.release import build_release, check_dependency, validate_archive


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.domain = "example"
        self.directory = self.root / "custom_components" / self.domain
        self.directory.mkdir(parents=True)
        self.manifest = {
            "domain": self.domain,
            "version": "2026.10.1",
            "requirements": ["MeteoGalicia-API==0.1.8"],
        }
        self.write_manifest()
        (self.directory / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "hacs.json").write_text(
            json.dumps({"zip_release": True, "filename": "example.zip"}),
            encoding="utf-8",
        )
        self.archive = self.root / "example.zip"

    def write_manifest(self):
        (self.directory / "manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8"
        )

    def build(self, **kwargs):
        return build_release(
            self.root, self.domain, "v2026.10.01", self.archive, **kwargs
        )

    def test_flat_archive_preserves_translations_and_excludes_bytecode(self):
        (self.directory / "translations").mkdir()
        (self.directory / "translations" / "gl.json").write_text("{}", encoding="utf-8")
        (self.directory / "__pycache__").mkdir()
        (self.directory / "__pycache__" / "sensor.pyc").write_bytes(b"bytecode")
        (self.directory / ".secret").write_text("ignored", encoding="utf-8")
        self.build()
        with ZipFile(self.archive) as package:
            self.assertEqual(
                set(package.namelist()),
                {"manifest.json", "__init__.py", "translations/gl.json"},
            )

    def test_wrong_tag_cannot_create_archive(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            build_release(self.root, self.domain, "v2026.10.2", self.archive)
        self.assertFalse(self.archive.exists())

    def test_pr_validation_uses_manifest_instead_of_github_merge_ref(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "release.py"
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--domain",
                self.domain,
                "--use-manifest-version",
                "--output",
                str(self.archive),
            ],
            cwd=self.root,
            env={**os.environ, "GITHUB_REF_NAME": "40/merge", "GITHUB_OUTPUT": ""},
            check=True,
            capture_output=True,
        )
        validate_archive(self.archive, self.manifest)

    def test_wrong_hacs_filename_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Archive name"):
            build_release(self.root, self.domain, "2026.10.1", self.root / "wrong.zip")

    def test_archive_manifest_mismatch_is_rejected(self):
        self.build()
        changed = {**self.manifest, "version": "2026.10.0"}
        with self.assertRaisesRegex(ValueError, "differs"):
            validate_archive(self.archive, changed)

    def test_nested_archive_is_rejected(self):
        with ZipFile(self.archive, "w") as package:
            package.writestr("example/manifest.json", json.dumps(self.manifest))
            package.writestr("example/__init__.py", "")
        with self.assertRaisesRegex(ValueError, "ZIP root"):
            validate_archive(self.archive, self.manifest)

    def test_unsafe_archive_paths_are_rejected(self):
        self.build()
        with ZipFile(self.archive, "a") as package:
            package.writestr("../unexpected.py", "")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            validate_archive(self.archive, self.manifest)

    def test_unpublished_or_yanked_dependency_is_rejected(self):
        for urls in ([], [{"yanked": True}]):
            with (
                self.subTest(urls=urls),
                self.assertRaisesRegex(ValueError, "no available"),
            ):
                check_dependency(
                    self.manifest,
                    lambda version, urls=urls: {
                        "info": {"version": version},
                        "urls": urls,
                    },
                )

    def test_published_pinned_dependency_is_accepted(self):
        check_dependency(
            self.manifest,
            lambda version: {"info": {"version": version}, "urls": [{"yanked": False}]},
        )

    def test_unpinned_dependency_is_rejected(self):
        self.manifest["requirements"] = ["MeteoGalicia-API>=0.1.8"]
        with self.assertRaisesRegex(ValueError, "Pin exactly"):
            check_dependency(self.manifest)

    def test_integration_changes_require_version_bump_but_workflows_do_not(self):
        def git(*args):
            return subprocess.check_output(
                ["git", *args], cwd=self.root, text=True
            ).strip()

        git("init", "--quiet")
        git("add", ".")
        git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--quiet",
            "-m",
            "base",
        )
        base = git("rev-parse", "HEAD")
        (self.root / "workflow.yml").write_text("change", encoding="utf-8")
        git("add", ".")
        git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--quiet",
            "-m",
            "workflow",
        )
        self.build(base_ref=base)
        (self.directory / "__init__.py").write_text("# changed", encoding="utf-8")
        git("add", ".")
        git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--quiet",
            "-m",
            "code",
        )
        with self.assertRaisesRegex(ValueError, "newer manifest version"):
            self.build(base_ref=base)
        self.manifest["version"] = "2026.10.2"
        self.write_manifest()
        build_release(self.root, self.domain, "v2026.10.2", self.archive, base_ref=base)


if __name__ == "__main__":
    unittest.main()
