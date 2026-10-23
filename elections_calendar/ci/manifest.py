"""Reading an artifact's ``manifest.json`` and checking it against the files present (P119)."""

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Final

_DIGEST: Final = re.compile(r"[0-9a-f]{64}")
_MAX_PATH: Final = 255
_SHOWN: Final = 120
_NAME: Final = "manifest.json"


class ManifestError(ValueError):
    """The artifact does not match its manifest, or the manifest is unusable."""


def safe_path(path: str) -> bool:
    """Whether ``path`` is a relative, ``/``-separated path with no trick in it."""
    if not path or len(path) > _MAX_PATH or path.startswith("/"):
        return False
    if any(c in ("\\", ":") or ord(c) < 0x20 or ord(c) == 0x7F for c in path):
        return False
    return all(part not in ("", ".", "..") for part in path.split("/"))


def _shown(path: str) -> str:
    return repr(path)[:_SHOWN]


def _load(root: Path) -> dict[str, str]:
    path = root / _NAME
    if not path.is_file():
        raise ManifestError("manifest.json is missing")
    try:
        data: Any = json.loads(path.read_bytes().decode("utf-8"))
    except OSError, ValueError, RecursionError:  # the first two cover bad UTF-8 and bad JSON
        raise ManifestError("manifest.json is malformed") from None
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "files"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or not isinstance(data["files"], dict)
        or not all(
            isinstance(k, str) and isinstance(v, str) and _DIGEST.fullmatch(v)
            for k, v in data["files"].items()
        )
    ):
        raise ManifestError("manifest.json is malformed")
    return dict(sorted(data["files"].items()))


def _present(root: Path) -> list[str]:
    """Every regular file under ``root`` other than ``manifest.json``; a link raises."""
    entries: list[tuple[str, bool]] = []
    for here, dirs, files in os.walk(root, followlinks=False):
        for name in (*dirs, *files):
            full = Path(here, name)
            entries.append((full.relative_to(root).as_posix(), full.is_symlink()))
    regular: list[str] = []
    for rel, is_link in sorted(entries):
        if is_link:
            raise ManifestError(f"a link is not a file: {_shown(rel)}")
        if (root / rel).is_file() and rel != _NAME:
            regular.append(rel)
    return regular


def read_manifest(root: Path) -> dict[str, str]:
    """``{posix path: sha256}`` of ``root``'s manifest after seven checks (``ManifestError``)."""
    files = _load(root)
    for key in files:
        if not safe_path(key):
            raise ManifestError(f"manifest lists an unsafe path: {_shown(key)}")
    present = _present(root)
    for rel in present:
        if rel not in files:
            raise ManifestError(f"a file is not in the manifest: {_shown(rel)}")
    for key in files:
        if not (root.joinpath(*key.split("/"))).is_file():
            raise ManifestError(f"a file in the manifest is missing: {_shown(key)}")
    for key, digest in files.items():
        actual = hashlib.sha256(root.joinpath(*key.split("/")).read_bytes()).hexdigest()
        if actual != digest:
            raise ManifestError(f"a file does not match the manifest: {_shown(key)}")
    return files
