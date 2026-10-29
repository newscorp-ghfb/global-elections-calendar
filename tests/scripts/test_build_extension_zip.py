"""The checked, reproducible extension ZIP (Plan 5b-2 Task 7; P148, R54, R62)."""

import hashlib
import json
import os
import platform
import re
import shutil
import zipfile
import zlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from scripts.build_extension_zip import (
    COMPARED_KEYS,
    EXTENSION,
    FILES,
    V1_PERMISSIONS,
    VERSION,
    ZIP_NAME,
    ZipCheckError,
    build,
    problems,
    release_row,
)
from tests.support.extension import ROOT, V1_EXTENSION


def _copy(tmp_path: Path, name: str = "ext") -> Path:
    folder = tmp_path / name
    shutil.copytree(EXTENSION, folder)
    return folder


def _manifest(folder: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    return loaded


def _write_manifest(folder: Path, manifest: dict[str, Any]) -> None:
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def test_every_extension_file_is_listed() -> None:
    assert problems(EXTENSION) == []
    assert FILES[0] == "manifest.json"
    assert len(set(FILES)) == len(FILES)


def test_the_zip_is_built_from_the_explicit_list(tmp_path: Path) -> None:
    path, digest = build(EXTENSION, tmp_path / "dist")
    assert path == tmp_path / "dist" / ZIP_NAME
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        assert [i.filename for i in infos] == list(FILES)
        for info in infos:
            assert archive.read(info) == (EXTENSION / info.filename).read_bytes()
            assert not info.is_dir()
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.create_system == 3
            assert info.external_attr == 0o100644 << 16
            assert info.compress_type == zipfile.ZIP_DEFLATED


def test_the_zip_is_reproducible(tmp_path: Path) -> None:
    digests: list[str] = []
    for name, when in (("a", datetime(2001, 1, 1, tzinfo=UTC)), ("b", datetime(2031, 6, 15, tzinfo=UTC))):
        folder = _copy(tmp_path, name)
        stamp = when.timestamp()
        for item in folder.rglob("*"):
            os.utime(item, (stamp, stamp))
        digests.append(build(folder, tmp_path / f"dist-{name}")[1])
    assert digests[0] == digests[1]


def _edit_popup(folder: Path) -> None:
    page = folder / "popup.html"
    page.write_text(
        page.read_text(encoding="utf-8").replace('src="popup.js"', 'src="missing.js"'), encoding="utf-8"
    )


def _edit_version(folder: Path) -> None:
    manifest = _manifest(folder)
    manifest["version"] = "1.0.2"
    _write_manifest(folder, manifest)


def _edit_tabs(folder: Path) -> None:
    manifest = _manifest(folder)
    manifest["permissions"].append("tabs")
    _write_manifest(folder, manifest)


def _edit_host(folder: Path) -> None:
    manifest = _manifest(folder)
    manifest["host_permissions"].append("https://example.com/*")
    _write_manifest(folder, manifest)


def _edit_key(folder: Path) -> None:
    manifest = _manifest(folder)
    manifest["key"] = "MIIB"
    _write_manifest(folder, manifest)


def _edit_stray(folder: Path) -> None:
    (folder / "notes.txt").write_text("stray\n", encoding="utf-8")


def _edit_delete(folder: Path) -> None:
    (folder / "lib" / "a11y.js").unlink()


REFUSALS: list[tuple[str, Callable[[Path], None], str]] = [
    ("missing asset", _edit_popup, "popup.html references missing.js"),
    ("old version", _edit_version, "version is 1.0.2, expected 2.0.0"),
    ("tabs permission", _edit_tabs, "permissions differs from v1.0.2's"),
    ("added host", _edit_host, "host_permissions differs from v1.0.2's"),
    ("a key", _edit_key, "key differs from v1.0.2's"),
    ("stray file", _edit_stray, "not in FILES: notes.txt"),
    ("deleted listed file", _edit_delete, "listed file is missing: lib/a11y.js"),
]


@pytest.mark.parametrize(("edit", "expected"), [(r[1], r[2]) for r in REFUSALS], ids=[r[0] for r in REFUSALS])
def test_zip_checks_refuse(tmp_path: Path, edit: Callable[[Path], None], expected: str) -> None:
    folder = _copy(tmp_path)
    edit(folder)
    assert any(expected in line for line in problems(folder)), problems(folder)
    with pytest.raises(ZipCheckError, match=re.escape(expected)):
        build(folder, tmp_path / "dist")
    assert not (tmp_path / "dist" / ZIP_NAME).exists()


def test_the_permission_literal_matches_the_v1_fixture() -> None:
    was = json.loads((V1_EXTENSION / "manifest.json").read_text(encoding="utf-8"))
    assert len(COMPARED_KEYS) == 10
    for key in COMPARED_KEYS:
        assert V1_PERMISSIONS.get(key) == was.get(key), key
    assert VERSION == "2.0.0"
    assert f"Global_Elections_Calendar_v{VERSION}.zip" == ZIP_NAME


def test_the_manifest_may_be_absent_or_broken(tmp_path: Path) -> None:
    folder = _copy(tmp_path)
    (folder / "manifest.json").unlink()
    assert any("manifest.json is not at the root" in line for line in problems(folder))
    (folder / "manifest.json").write_text("{", encoding="utf-8")
    assert any("manifest.json is not valid JSON" in line for line in problems(folder))


def test_the_release_row_names_the_toolchain() -> None:
    digest = "ab" * 32
    row = release_row(digest, 31)
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    releases = (ROOT / "RELEASES.md").read_text(encoding="utf-8")
    header = next(line for line in releases.splitlines() if line.startswith("| Version |"))
    assert len(cells) == len(header.strip().strip("|").split("|")) == 9
    assert cells[0] == VERSION
    assert cells[2] == hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest()
    assert cells[3] == hashlib.sha256((ROOT / "requirements-dev.txt").read_bytes()).hexdigest()
    assert digest in cells[4]
    assert platform.python_version() in cells[4]
    assert zlib.ZLIB_RUNTIME_VERSION in cells[4]
    assert cells[5] == "31"
    assert cells[6:] == ["<destination>", "<date>", "<approved by>"]


def test_references_follow_the_rules(tmp_path: Path) -> None:
    folder = _copy(tmp_path)
    page = folder / "help.html"
    original = page.read_text(encoding="utf-8")
    harmless = (
        '<a href="https://example.com/x">a</a><a href="chrome://extensions">b</a>'
        '<a href="#top">c</a><img src="//cdn.example.com/i.png"><a href="mailto:a@b.c">d</a>'
        '<img src="data:image/png;base64,AAAA"><link href="popup.html?x=1#y">'
    )
    page.write_text(original.replace("</body>", harmless + "</body>"), encoding="utf-8")
    assert problems(folder) == []

    page.write_text(original.replace("</body>", '<img src="../escape.png"></body>'), encoding="utf-8")
    assert problems(folder) == ["help.html references ../escape.png, which is outside the folder"]

    page.write_text(original, encoding="utf-8")
    script = folder / "lib" / "a11y.js"
    script.write_text('import {\n  a,\n} from "./nope.js";\n' + script.read_text(encoding="utf-8"), encoding="utf-8")
    assert problems(folder) == ["lib/a11y.js references ./nope.js, which is not in the folder"]
