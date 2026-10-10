"""Build and verify a HACS archive before publishing it (standard library only)."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
from urllib.request import urlopen
from zipfile import ZIP_DEFLATED, ZipFile

MANIFEST_FILE = "manifest.json"


def version_tuple(version):
    """Compare release tags and manifest versions, including padded CalVer."""
    if not isinstance(version, str) or not re.fullmatch(r"v?\d+\.\d+\.\d+", version):
        raise ValueError(f"Invalid release version: {version!r}")
    return tuple(int(part) for part in version.removeprefix("v").split("."))


def read_manifest(root, domain):
    manifest = json.loads(
        (root / "custom_components" / domain / MANIFEST_FILE).read_text(
            encoding="utf-8"
        )
    )
    if manifest.get("domain") != domain:
        raise ValueError("Manifest domain does not match the integration")
    version_tuple(manifest.get("version"))
    return manifest


def check_dependency(manifest, lookup=None):
    """Require an exact, published API version before attaching a release ZIP."""
    requirements = manifest.get("requirements", [])
    pins = [
        item for item in requirements if item.lower().startswith("meteogalicia-api")
    ]
    if len(pins) != 1 or not re.fullmatch(
        r"MeteoGalicia-API==\d+\.\d+\.\d+", pins[0], re.IGNORECASE
    ):
        raise ValueError("Pin exactly one MeteoGalicia-API version with ==")
    version = pins[0].split("==", 1)[1]
    if lookup is None:
        with urlopen(
            f"https://pypi.org/pypi/MeteoGalicia-API/{version}/json", timeout=30
        ) as response:
            published = json.load(response)
    else:
        published = lookup(version)
    if published.get("info", {}).get("version") != version or not any(
        not item.get("yanked", False) for item in published.get("urls", [])
    ):
        raise ValueError(
            f"MeteoGalicia-API {version} has no available distribution on PyPI"
        )


def integration_files(directory):
    """Return release files, ignoring local caches and temporary files."""
    files = {}
    for source in sorted(directory.rglob("*")):
        relative = source.relative_to(directory)
        if (
            source.is_file()
            and not any(
                part.startswith(".") or part == "__pycache__" for part in relative.parts
            )
            and source.suffix not in {".pyc", ".pyo"}
        ):
            files[relative.as_posix()] = source
    return files


def check_version_bump(root, domain, manifest, base_directory):
    """Reject integration changes with the same or an older version than the PR base."""
    previous = read_manifest(base_directory, domain)

    def contents(checkout):
        return {
            name: hashlib.sha256(source.read_bytes()).digest()
            for name, source in integration_files(
                checkout / "custom_components" / domain
            ).items()
        }

    if contents(root) == contents(base_directory):
        return
    if version_tuple(manifest["version"]) <= version_tuple(previous["version"]):
        raise ValueError(
            "Integration changes require a newer manifest version before merging"
        )


def validate_archive(archive, manifest):
    """Verify CRCs, a flat HACS layout and the exact manifest used for the release."""
    with ZipFile(archive) as package:
        names = package.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive entries")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise ValueError("Unsafe archive path")
        if not {MANIFEST_FILE, "__init__.py"}.issubset(names):
            raise ValueError(
                "HACS requires manifest.json and __init__.py at the ZIP root"
            )
        if package.testzip() is not None:
            raise ValueError("Corrupt archive")
        if json.loads(package.read(MANIFEST_FILE)) != manifest:
            raise ValueError("Archive manifest differs from the release manifest")


def build_release(
    root, domain, tag, output, verify_dependencies=False, base_directory=None
):
    """Validate the version, dependency and contents, then return a verified ZIP."""
    manifest = read_manifest(root, domain)
    if version_tuple(tag) != version_tuple(manifest["version"]):
        raise ValueError(
            f"Tag {tag} does not match manifest version {manifest['version']}"
        )
    hacs = json.loads((root / "hacs.json").read_text(encoding="utf-8"))
    if hacs.get("zip_release") is not True or hacs.get("filename") != output.name:
        raise ValueError(
            "Archive name must match hacs.json and zip_release must be true"
        )
    if base_directory:
        check_version_bump(root, domain, manifest, base_directory)
    if verify_dependencies:
        check_dependency(manifest)
    directory = root / "custom_components" / domain
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as package:
        for name, source in integration_files(directory).items():
            package.write(source, name)
    validate_archive(output, manifest)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--tag")
    parser.add_argument("--use-manifest-version", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verify-dependencies", action="store_true")
    parser.add_argument("--base-directory", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    tag = (
        read_manifest(root, args.domain)["version"]
        if args.use_manifest_version
        else args.tag or os.environ.get("GITHUB_REF_NAME", "").removeprefix("publish/")
    )
    if not tag:
        tag = read_manifest(root, args.domain)["version"]
    build_release(
        root,
        args.domain,
        tag,
        args.output,
        args.verify_dependencies,
        args.base_directory,
    )
    if output_file := os.environ.get("GITHUB_OUTPUT"):
        with open(output_file, "a", encoding="utf-8") as output:
            output.write(f"tag={tag}\n")
    print(f"Verified {args.output} for {tag}")


if __name__ == "__main__":
    main()
