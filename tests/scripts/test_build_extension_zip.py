"""The checked, reproducible extension ZIP (Plan 5b-2 Task 7; P148, R54, R62)."""

import hashlib
import json
import os
import platform
import re
import shutil
import struct
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
    main,
    problems,
    release_row,
)
from tests.support.extension import ROOT, V1_EXTENSION
from tests.support.git_repos import git


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


def _deflate_9(data: bytes) -> bytes:
    packer = zlib.compressobj(9, zlib.DEFLATED, -15)
    return packer.compress(data) + packer.flush()


def _raw_stream(path: Path, info: zipfile.ZipInfo) -> bytes:
    """The entry's compressed bytes, read from after its local header."""
    raw = path.read_bytes()
    start = info.header_offset
    name_length, extra_length = struct.unpack("<HH", raw[start + 26 : start + 30])
    begin = start + 30 + name_length + extra_length
    return raw[begin : begin + info.compress_size]


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
            assert _raw_stream(path, info) == _deflate_9(archive.read(info))


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
    ("missing asset", _edit_popup, "popup.html references missing.js, which is not in the folder"),
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
    assert expected in problems(folder)
    with pytest.raises(ZipCheckError, match=rf"(^|\n){re.escape(expected)}($|\n)"):
        build(folder, tmp_path / "dist")
    assert not (tmp_path / "dist" / ZIP_NAME).exists()


def test_the_permission_literal_matches_the_v1_fixture() -> None:
    was = json.loads((V1_EXTENSION / "manifest.json").read_text(encoding="utf-8"))
    assert COMPARED_KEYS == (
        "permissions",
        "host_permissions",
        "optional_permissions",
        "optional_host_permissions",
        "content_scripts",
        "externally_connectable",
        "web_accessible_resources",
        "key",
        "content_security_policy",
        "update_url",
    )
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

    page.write_text(original, encoding="utf-8")
    script.write_text(script.read_text(encoding="utf-8").split("\n", 3)[3], encoding="utf-8")
    assert problems(folder) == []

    kept = script.read_text(encoding="utf-8")
    script.write_text('import "/lib/nope.js";\n' + kept, encoding="utf-8")
    assert problems(folder) == ["lib/a11y.js references /lib/nope.js, which is not in the folder"]
    script.write_text('import "//cdn.example.com/x.js";\n' + kept, encoding="utf-8")
    assert problems(folder) == []
    script.write_text(kept, encoding="utf-8")

    page.write_text(original.replace("</body>", "<img src=missing.png></body>"), encoding="utf-8")
    assert problems(folder) == ["help.html references missing.png, which is not in the folder"]

    page.write_text(original.replace("</body>", '<img src="/lib/a11y.js"></body>'), encoding="utf-8")
    assert problems(folder) == []
    page.write_text(original.replace("</body>", '<img src="/lib/nope.js"></body>'), encoding="utf-8")
    assert problems(folder) == ["help.html references /lib/nope.js, which is not in the folder"]
    page.write_text(original, encoding="utf-8")

    manifest = _manifest(folder)
    manifest["action"]["default_icon"] = "icons/missing.png"
    _write_manifest(folder, manifest)
    assert problems(folder) == ["manifest.json references icons/missing.png, which is not in the folder"]
    manifest["action"]["default_icon"] = "icons/icon16.png"
    _write_manifest(folder, manifest)
    assert problems(folder) == []


def test_an_unreadable_file_is_a_problem_not_a_crash(tmp_path: Path) -> None:
    folder = _copy(tmp_path)
    with (folder / "lib" / "a11y.js").open("ab") as handle:
        handle.write(b"\xe9\n")
    found = problems(folder)
    assert len(found) == 1
    assert found[0].startswith("lib/a11y.js could not be read as UTF-8 text: ")
    with pytest.raises(ZipCheckError, match="lib/a11y.js could not be read"):
        build(folder, tmp_path / "dist")


# --- the guarded release build (Plan 5c Task 4; P154, R65, R62) -----------------------------------


def _release_repo(tmp_path: Path) -> tuple[Path, str]:
    """A temporary repository holding ``extension/`` and the requirements; its HEAD SHA."""
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copytree(EXTENSION, repo / "extension")
    for name in ("requirements.txt", "requirements-dev.txt"):
        shutil.copy(ROOT / name, repo / name)
    (repo / ".gitignore").write_text("dist/\n", encoding="utf-8", newline="")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "--all")
    git(repo, "commit", "-q", "-m", "release candidate")
    return repo, git(repo, "rev-parse", "HEAD")


def _untracked(repo: Path) -> None:
    (repo / "x.txt").write_text("x\n", encoding="utf-8", newline="")


def _untracked_dir(repo: Path) -> None:
    (repo / "new").mkdir()
    (repo / "new" / "x.txt").write_text("x\n", encoding="utf-8", newline="")


def _modified(repo: Path) -> None:
    with (repo / "extension" / "popup.js").open("a", encoding="utf-8", newline="") as handle:
        handle.write("// edited\n")


def _nothing(repo: Path) -> None:
    return None


RELEASE_CASES: list[tuple[str, Callable[[Path], None], str | None, int, str]] = [
    ("ok", _nothing, None, 0, ""),
    (
        "untracked",
        _untracked,
        None,
        1,
        "the working tree is not clean (1 changed or untracked, first: x.txt)",
    ),
    (
        "untracked_dir",
        _untracked_dir,
        None,
        1,
        "(1 changed or untracked, first: new/x.txt)",
    ),
    (
        "modified",
        _modified,
        None,
        1,
        "the working tree is not clean (1 changed or untracked, first: extension/popup.js)",
    ),
    ("other_commit", _nothing, "0" * 40, 1, "HEAD is {head}, not the release commit " + "0" * 40),
    ("short", _nothing, "abc1234", 1, "--release-sha must be the full 40-character commit SHA"),
]


@pytest.mark.parametrize(
    ("change", "release_sha", "exit_code", "message"),
    [pytest.param(c, r, e, m, id=i) for i, c, r, e, m in RELEASE_CASES],
)
def test_a_release_build_needs_a_clean_tree_at_the_release_commit(
    change: Callable[[Path], None],
    release_sha: str | None,
    exit_code: int,
    message: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, head = _release_repo(tmp_path)
    change(repo)
    code = main(["--release-sha", release_sha or head, "--repo", str(repo)])
    captured = capsys.readouterr()
    assert code == exit_code
    zips = list((repo / "dist").glob("*.zip"))
    if exit_code == 0:
        assert len(zips) == 1
        assert captured.err == ""
    else:
        assert message.format(head=head) in captured.err
        assert zips == []
        assert "| 2.0.0 |" not in captured.out


def test_a_release_build_works_from_a_detached_head(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, head = _release_repo(tmp_path)
    git(repo, "checkout", "-q", "--detach", "HEAD")
    assert main(["--release-sha", head, "--repo", str(repo)]) == 0
    assert f"| {VERSION} | {head} |" in capsys.readouterr().out


def test_the_release_row_carries_the_code_sha(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, head = _release_repo(tmp_path)
    assert main(["--release-sha", head, "--repo", str(repo)]) == 0
    out = capsys.readouterr().out
    assert f"| {VERSION} | {head} |" in out
    assert "<code SHA>" not in out
    assert "Development build" not in out
    assert main(["--repo", str(repo)]) == 0
    out = capsys.readouterr().out
    assert f"| {VERSION} | <code SHA> |" in out
    assert "Development build: the RELEASES.md row needs --release-sha" in out


def test_the_release_row_reads_the_requirements_of_the_given_repo(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_bytes(b"a\n")
    (tmp_path / "requirements-dev.txt").write_bytes(b"b\n")
    cells = release_row("ab" * 32, 31, root=tmp_path).strip().strip("|").split("|")
    assert cells[2].strip() == hashlib.sha256(b"a\n").hexdigest()
    assert cells[3].strip() == hashlib.sha256(b"b\n").hexdigest()


def test_a_release_build_outside_a_repository_is_an_exit_1_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    code = main(["--release-sha", "a" * 40, "--repo", str(plain)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err.strip()
    assert "Traceback" not in captured.err
    assert captured.out == ""
