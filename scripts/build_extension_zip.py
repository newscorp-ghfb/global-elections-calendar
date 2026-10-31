"""Build the checked extension ZIP, dist/Global_Elections_Calendar_v2.0.0.zip (Plan 5b-2 Task 7).

The ZIP is built from the explicit list ``FILES`` and only after four checks pass:

- the manifest is at the root;
- every referenced asset is present (the manifest's icons, popup, options page and worker;
  ``src`` and ``href`` in each HTML file; static ``import`` and ``export ... from`` specifiers in
  each JS file);
- the version is ``VERSION``;
- the permission-related manifest keys equal v1.0.2's.

``FILES`` must also equal the folder: a file under ``extension/`` that is not listed is refused.

The bytes are reproducible for one Python minor version and one zlib version: entries in ``FILES``
order, dated 1980-01-01, mode 0644, ``create_system`` 3, deflate level 9, no directory entries.
Another toolchain carries no identical-byte promise, so the printed row names both versions.

The script prints the ``RELEASES.md`` row and does not write it (5c does, with the release's date
and approval). The row carries a code SHA only from a guarded build (R65, P154):

    .venv\\Scripts\\python.exe -m scripts.build_extension_zip --release-sha <40-hex SHA>

This refuses a SHA that is not 40 lowercase hex, a working tree with anything changed or untracked,
and a HEAD that is another commit (a detached HEAD at that commit is fine). Without
``--release-sha`` the build is a development build and the row keeps ``<code SHA>``.
"""

import argparse
import hashlib
import json
import os
import platform
import posixpath
import re
import sys
import tempfile
import zipfile
import zlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from elections_calendar.ci.git import Git, GitError

ROOT: Final = Path(__file__).resolve().parent.parent
EXTENSION: Final = ROOT / "extension"
DIST: Final = ROOT / "dist"

VERSION: Final = "2.0.0"
ZIP_NAME: Final = f"Global_Elections_Calendar_v{VERSION}.zip"

# Relative to extension/, POSIX paths, the manifest first.
FILES: Final[tuple[str, ...]] = (
    "manifest.json",
    "background.js",
    "help.html",
    "icons/icon128.png",
    "icons/icon16.png",
    "icons/icon48.png",
    "lib/a11y.js",
    "lib/attention.js",
    "lib/count.js",
    "lib/dates.js",
    "lib/details.js",
    "lib/health.js",
    "lib/labels.js",
    "lib/legacy.js",
    "lib/links.js",
    "lib/load.js",
    "lib/order.js",
    "lib/pins.js",
    "lib/render.js",
    "lib/schema.js",
    "lib/validate.js",
    "lib/worker.js",
    "options.css",
    "options.html",
    "options.js",
    "places.json",
    "popup.html",
    "popup.js",
    "schemas/feed-v2.schema.json",
    "schemas/status-v1.schema.json",
    "styles.css",
)

# The manifest keys that carry permissions or reach (v1.0.2's values; absent keys are absent here).
COMPARED_KEYS: Final[tuple[str, ...]] = (
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
V1_PERMISSIONS: Final[dict[str, Any]] = {
    "permissions": ["storage", "alarms"],
    "host_permissions": ["https://raw.githubusercontent.com/*"],
}

_FULL_SHA: Final = re.compile(r"[0-9a-f]{40}")
_ENTRY_TIME: Final = (1980, 1, 1, 0, 0, 0)
_ENTRY_MODE: Final = 0o100644 << 16
_SCHEME: Final = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_ATTRIBUTE: Final = re.compile(
    r"""\b(?:src|href)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'<>=`]+))""", re.IGNORECASE
)
_BLOCK_COMMENT: Final = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT: Final = re.compile(r"^[ \t]*//.*$", re.MULTILINE)
_FROM: Final = re.compile(r"""\b(?:import|export)\b[^;"'`]*?\bfrom\s*["']([^"']+)["']""")
_BARE_IMPORT: Final = re.compile(r"""\bimport\s*["']([^"']+)["']""")


class ZipCheckError(Exception):
    """The folder failed a check; the message lists the problems, one per line."""


def _files_under(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


def _resolve(origin: str, reference: str) -> str | None:
    """The folder-relative path a reference from ``origin`` names; None if it leaves the folder.

    A leading ``/`` is the folder root (an extension page's ``/popup.js`` is valid).
    """
    if reference.startswith("/"):
        joined = posixpath.normpath(reference.lstrip("/"))
    else:
        joined = posixpath.normpath(posixpath.join(posixpath.dirname(origin), reference))
    return None if joined == ".." or joined.startswith("../") else joined


def _check_reference(folder: Path, origin: str, reference: str, found: list[str]) -> None:
    target = _resolve(origin, reference)
    if target is None:
        found.append(f"{origin} references {reference}, which is outside the folder")
    elif not (folder / target).is_file():
        found.append(f"{origin} references {reference}, which is not in the folder")


def _manifest_references(manifest: dict[str, Any]) -> list[str]:
    refs: list[str] = []

    def take(value: Any) -> None:
        if isinstance(value, str):
            refs.append(value)

    action = manifest.get("action")
    action_icons = action.get("default_icon") if isinstance(action, dict) else None
    for table in (manifest.get("icons"), action_icons):
        if isinstance(table, dict):
            for value in table.values():
                take(value)
        else:
            take(table)  # Chrome also accepts a single path for default_icon
    if isinstance(action, dict):
        take(action.get("default_popup"))
    options = manifest.get("options_ui")
    if isinstance(options, dict):
        take(options.get("page"))
    background = manifest.get("background")
    if isinstance(background, dict):
        take(background.get("service_worker"))
    return refs


def _html_references(text: str) -> list[str]:
    refs: list[str] = []
    for match in _ATTRIBUTE.finditer(text):
        value = (match.group(1) or match.group(2) or match.group(3) or "").strip()
        if value == "" or value.startswith(("#", "//")) or _SCHEME.match(value):
            continue
        value = re.split(r"[?#]", value, maxsplit=1)[0]
        if value != "":
            refs.append(value)
    return refs


def _js_references(text: str) -> list[str]:
    text = _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", text))
    found = [*_FROM.findall(text), *_BARE_IMPORT.findall(text)]
    return [
        spec
        for spec in found
        if spec.startswith(("./", "../")) or (spec.startswith("/") and not spec.startswith("//"))
    ]


def problems(folder: Path) -> list[str]:
    """Every failed check, one line each (an empty list means the folder may be released).

    Known limits of the reference scan, which is not a JS tokenizer: comments are stripped without
    regard to strings, so a ``/*`` inside a string can hide a later import; and import-like text
    in a string or in a trailing ``//`` comment (block comments and whole-line ``//`` comments
    are stripped first) is followed. The second fails safe (the build refuses); the first is
    covered by the extension suite, which loads every module.
    """
    found: list[str] = []
    present = _files_under(folder)
    for name in FILES:
        if name not in present:
            found.append(f"listed file is missing: {name}")
    for name in present:
        if name not in FILES:
            found.append(f"not in FILES: {name}")

    manifest: dict[str, Any] | None = None
    if "manifest.json" not in present:
        found.append("manifest.json is not at the root")
    else:
        try:
            loaded = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded = None
        if isinstance(loaded, dict):
            manifest = loaded
        else:
            found.append("manifest.json is not valid JSON (an object is expected)")
    if manifest is not None:
        if manifest.get("version") != VERSION:
            found.append(f"version is {manifest.get('version')}, expected {VERSION}")
        for key in COMPARED_KEYS:
            if manifest.get(key) != V1_PERMISSIONS.get(key):
                found.append(f"{key} differs from v1.0.2's")
        for reference in _manifest_references(manifest):
            _check_reference(folder, "manifest.json", reference, found)

    for name in present:
        if name.endswith((".html", ".htm")):
            references = _html_references
        elif name.endswith(".js"):
            references = _js_references
        else:
            continue
        try:
            text = (folder / name).read_text(encoding="utf-8")
        except (OSError, ValueError) as err:
            found.append(f"{name} could not be read as UTF-8 text: {err}")
            continue
        for reference in references(text):
            _check_reference(folder, name, reference, found)
    return found


def build(folder: Path = EXTENSION, out_dir: Path = DIST) -> tuple[Path, str]:
    """Write ``out_dir / ZIP_NAME`` after the checks pass; return it with its SHA-256."""
    found = problems(folder)
    if found:
        raise ZipCheckError("\n".join(found))
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / ZIP_NAME
    handle, temporary = tempfile.mkstemp(dir=out_dir, prefix=ZIP_NAME, suffix=".tmp")
    os.close(handle)
    scratch = Path(temporary)
    try:
        with zipfile.ZipFile(scratch, "w") as archive:
            for name in FILES:
                info = zipfile.ZipInfo(name, _ENTRY_TIME)
                info.create_system = 3
                info.external_attr = _ENTRY_MODE
                archive.writestr(
                    info,
                    (folder / name).read_bytes(),
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
        os.replace(scratch, target)
    except BaseException:
        scratch.unlink(missing_ok=True)
        raise
    return target, hashlib.sha256(target.read_bytes()).hexdigest()


def release_row(
    sha256: str, count: int, *, root: Path = ROOT, code_sha: str | None = None
) -> str:
    """The ``RELEASES.md`` row for this build; 5c fills the placeholders (R62).

    ``code_sha`` is set only by a guarded build (``--release-sha``, R65); without it the cell keeps
    ``<code SHA>``. The requirements digests are read from ``root``.
    """
    requirements = hashlib.sha256((root / "requirements.txt").read_bytes()).hexdigest()
    dev = hashlib.sha256((root / "requirements-dev.txt").read_bytes()).hexdigest()
    zip_cell = f"{sha256} (Python {platform.python_version()}, zlib {zlib.ZLIB_RUNTIME_VERSION})"
    cells = [
        VERSION,
        code_sha or "<code SHA>",
        requirements,
        dev,
        zip_cell,
        str(count),
        "<destination>",
        "<date>",
        "<approved by>",
    ]
    return "| " + " | ".join(cells) + " |"


def release_problems(repo: Path, release_sha: str) -> list[str]:
    """Why ``repo`` may not be released as ``release_sha`` (R65, P154); empty when it may.

    A bad SHA format is reported alone. Otherwise the working tree must hold nothing changed or
    untracked (``dist/`` is git-ignored), and ``HEAD`` must be ``release_sha``; a detached HEAD
    is fine. Raises ``GitError`` when ``repo`` cannot be read by git.
    """
    if not _FULL_SHA.fullmatch(release_sha):
        return ["--release-sha must be the full 40-character commit SHA"]
    git = Git(repo)
    found: list[str] = []
    # ``Git.run`` strips its output, so the first line may have lost its leading space
    # (" M path" arrives as "M path"): take each path after the status word, not at a column.
    changed = git.run("status", "--porcelain", "--untracked-files=all").splitlines()
    if changed:
        first = changed[0].lstrip().split(None, 1)[1]
        found.append(
            f"the working tree is not clean ({len(changed)} changed or untracked, first: {first})"
        )
    head = git.run("rev-parse", "HEAD")
    if head != release_sha:
        found.append(f"HEAD is {head}, not the release commit {release_sha}")
    return found


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.build_extension_zip",
        description=f"Build dist/{ZIP_NAME} from <repo>/extension and print its RELEASES.md row.",
    )
    parser.add_argument(
        "--release-sha",
        metavar="HEX",
        help="the full release commit SHA: a guarded release build, which fills the row's code SHA",
    )
    parser.add_argument("--repo", type=Path, default=ROOT, help="the repository (default: this)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exit_:
        return exit_.code if isinstance(exit_.code, int) else 2
    repo: Path = args.repo
    release_sha: str | None = args.release_sha
    if release_sha is not None:
        try:
            refused = release_problems(repo, release_sha)
        except GitError as err:
            refused = [str(err)]
        if refused:
            for line in refused:
                print(line, file=sys.stderr)
            return 1
    try:  # read before building, so a missing file leaves no ZIP behind
        for name in ("requirements.txt", "requirements-dev.txt"):
            (repo / name).read_bytes()
    except OSError as err:
        print(f"cannot read {err.filename or err}: {err.strerror or err}", file=sys.stderr)
        return 1
    try:
        path, digest = build(repo / "extension", repo / "dist")
    except ZipCheckError as err:
        for line in str(err).splitlines():
            print(line, file=sys.stderr)
        return 1
    print(f"ZIP: {path}")
    print(f"SHA-256: {digest}")
    print(f"Files: {len(FILES)}")
    print(
        "Checks passed: the manifest is at the root; every referenced asset is present; "
        f"the version is {VERSION}; the permissions equal v1.0.2's; FILES equals the folder."
    )
    print("RELEASES.md row (not written; fill the placeholders at release):")
    print(release_row(digest, len(FILES), root=repo, code_sha=release_sha))
    if release_sha is None:
        print("Development build: the RELEASES.md row needs --release-sha")
    return 0


if __name__ == "__main__":
    sys.exit(main())
