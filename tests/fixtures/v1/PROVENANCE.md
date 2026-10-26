# v1 fixtures

## update-elections.yml

The v1 workflow as committed at `ff30417`: 886 bytes. It runs daily at 00:00 UTC and on dispatch
(no `push` trigger), never reads `PAUSE_PUBLISHING`, and its one `git add` adds only
`elections.json`. The rollback test (Plan 5a Task 8) uses it as the `pre-v2` workflow, because
those facts are what "v1 is the writer after the restore" rests on (P123).

Command (from the repository root; Task 7 has since rewritten the working-tree workflow, so this
reads the blob):

```
git -c core.autocrlf=false cat-file blob ff30417:.github/workflows/update-elections.yml > tests/fixtures/v1/update-elections.yml
```

SHA-256: `a89ac40882d76a9414f67d7f6469b975639835396cc8413cddb7bd43a0667906`

`.gitattributes` keeps `tests/fixtures/**` byte-exact (`-text`).

## extension/

The v1.0.2 extension as committed at `ff30417` (byte-identical at `319a292`): 12 files, 95,447
bytes. The legacy-client test (Plan 5b-1 Task 1) loads it into Chromium to prove that a v1.0.2
client still renders the v2 feed, and a CI checkout (depth 1) does not have `ff30417` (P129).

Command (for each path of `git ls-tree -r --name-only ff30417 extension/`, from the repository
root; written by a bytes script, never through a shell redirection of text):

```
git -c core.autocrlf=false cat-file blob ff30417:extension/<path> > tests/fixtures/v1/extension/<path minus extension/>
```

| Path | Bytes | SHA-256 |
|---|---|---|
| `background.js` | 1,365 | `4f8d64798cd4d8aadbae57206c61994a11186ca2b085be1f07942c16fde63afa` |
| `help.html` | 22,949 | `0445967aef14851784278e9347c8e8a7c948d567538195e03080b516c984a7bf` |
| `icons/icon128.png` | 17,374 | `fd7a60e0de60c41bb2c643c9880b6bede360ee19294ee80f03f21dfd5df31b31` |
| `icons/icon16.png` | 599 | `2340f4bcc2c5abf10c5f800837624fcb8d8c038c83575f891dbc1eee8de04e15` |
| `icons/icon48.png` | 3,210 | `c4ff4e04ba1c491a249a7e5d8695b1afe0285558e253a3b220ab94ac30d70d1b` |
| `manifest.json` | 724 | `26668ccb37bbf76e4599a7d041a0fbebc97225b332b436ef179e3cdbe34a51c3` |
| `options.css` | 6,823 | `f2731d297c3f9f9661b90a87be216e821ead56a87bbb54307b69a2085a74e581` |
| `options.html` | 1,123 | `059f87b6b1d18e56d768f64bd5b707fc3910d93eaa8f0a5991a244b4fa046784` |
| `options.js` | 7,526 | `a9e5ed20fa947989847186d34069fec85e2540160ddd990516f4876a39b156d8` |
| `popup.html` | 6,326 | `47a52f247ce43112ba72e2c6cea0f9985ef6b396a3b14c20cf15f0e0938491d1` |
| `popup.js` | 14,250 | `9b0db4589d09320d9396d188a8018f500a5d605907188884ab968a19d9a923cf` |
| `styles.css` | 13,178 | `2ef2e9bd0fd737e7c4d02c5b6148ba34f426649760b246651d2fed56a69ae515` |
