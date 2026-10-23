import json
import os
from pathlib import Path

import pytest

from elections_calendar.ci.manifest import ManifestError, read_manifest, safe_path
from elections_calendar.publish import write_manifest
from tests.support.ci import make_artifact

DIGEST = "0" * 64


def _manifest(root: Path, files: object) -> None:
    (root / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "files": files}), encoding="utf-8"
    )


def _good(root: Path) -> Path:
    make_artifact(root)
    (root / "sub").mkdir()
    (root / "sub" / "a.json").write_text("{}", encoding="utf-8")
    write_manifest(root)
    return root


def _problem(root: Path) -> str:
    with pytest.raises(ManifestError) as caught:
        read_manifest(root)
    return str(caught.value)


def _make_link(target: Path, link: Path) -> None:
    try:
        os.symlink(target, link)
    except OSError as problem:  # Windows without the privilege to make links
        pytest.skip(f"cannot make a symbolic link here: {problem}")


def test_good_manifest_reads(tmp_path: Path) -> None:
    files = read_manifest(_good(tmp_path))
    assert list(files) == ["HEALTH.md", "sub/a.json", "verdict.json"]


@pytest.mark.parametrize(
    "key",
    ["../x", "/x", "a\\b", "C:x", "a/./b", "a//b", "", "a\nb", "a\x00b", "a\x7fb", "x" * 256],
)
def test_unsafe_keys_are_refused(tmp_path: Path, key: str) -> None:
    assert not safe_path(key)
    _manifest(tmp_path, {key: DIGEST})
    assert _problem(tmp_path).startswith("manifest lists an unsafe path: ")


@pytest.mark.parametrize(
    "key", ["a.json", "a/b.json", "x" * 255, "data/sources/osce/baseline.json"]
)
def test_safe_keys(key: str) -> None:
    assert safe_path(key)


def test_manifest_checks(tmp_path: Path) -> None:
    def fresh(name: str) -> Path:
        return _good(tmp_path / name)

    empty = tmp_path / "empty"
    empty.mkdir()
    assert _problem(empty) == "manifest.json is missing"

    root = fresh("not-utf8")
    (root / "manifest.json").write_bytes(b"\xff\xfe{")
    assert _problem(root) == "manifest.json is malformed"

    bad = {
        "notjson": "{",
        "list": "[]",
        "extra": json.dumps({"schema_version": 1, "files": {}, "x": 1}),
        "version": json.dumps({"schema_version": 2, "files": {}}),
        "bool": json.dumps({"schema_version": True, "files": {}}),
        "files-list": json.dumps({"schema_version": 1, "files": []}),
        "upper": json.dumps({"schema_version": 1, "files": {"a": "A" * 64}}),
        "short": json.dumps({"schema_version": 1, "files": {"a": "0" * 63}}),
        "nonstr": json.dumps({"schema_version": 1, "files": {"a": 5}}),
    }
    for name, text in bad.items():
        root = fresh(name)
        (root / "manifest.json").write_text(text, encoding="utf-8")
        assert _problem(root) == "manifest.json is malformed", name

    root = fresh("unsafe")
    _manifest(root, {**read_manifest(root), "../x": DIGEST})
    assert _problem(root) == "manifest lists an unsafe path: '../x'"

    root = fresh("leftover")
    (root / "HEALTH.md.tmp").write_text("x", encoding="utf-8")
    assert _problem(root) == "a file is not in the manifest: 'HEALTH.md.tmp'"

    root = fresh("extra-file")
    (root / "sub" / "b.json").write_text("{}", encoding="utf-8")
    assert _problem(root) == "a file is not in the manifest: 'sub/b.json'"

    root = fresh("missing-file")
    (root / "sub" / "a.json").unlink()
    assert _problem(root) == "a file in the manifest is missing: 'sub/a.json'"

    root = fresh("changed")
    (root / "sub" / "a.json").write_text("[]", encoding="utf-8")
    assert _problem(root) == "a file does not match the manifest: 'sub/a.json'"

    root = fresh("long")
    (root / ("n" * 150)).write_text("x", encoding="utf-8")
    assert len(_problem(root)) == len("a file is not in the manifest: ") + 120


def test_manifest_with_a_link(tmp_path: Path) -> None:
    root = _good(tmp_path)
    _make_link(root / "HEALTH.md", root / "link.md")
    assert _problem(root) == "a link is not a file: 'link.md'"


def test_manifest_with_a_linked_directory(tmp_path: Path) -> None:
    root = _good(tmp_path / "art")
    _make_link(root / "sub", root / "linked-dir")
    assert _problem(root) == "a link is not a file: 'linked-dir'"
