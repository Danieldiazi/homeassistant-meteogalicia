"""Ensure the locked CI environment matches direct and integration requirements."""

import json
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_requirements(requirements):
    """Reject stale locks when a direct pinned dependency changes."""
    for requirement in requirements:
        requirement = requirement.strip()
        if not requirement or requirement.startswith("#"):
            continue
        package, expected = requirement.split("==")
        actual = version(package)
        if actual != expected:
            raise SystemExit(
                f"{package}: expected {expected}, installed {actual}. "
                "Regenerate the dependency locks; see docs/development.md."
            )


if __name__ == "__main__":
    for filename in ("requirements_build.txt", "requirements_test.txt"):
        check_requirements((ROOT / filename).read_text(encoding="utf-8").splitlines())
    manifest = json.loads(
        (ROOT / "custom_components/meteogalicia/manifest.json").read_text(encoding="utf-8")
    )
    check_requirements(manifest["requirements"])
    print("Direct dependencies and manifest match the locked test environment.")
