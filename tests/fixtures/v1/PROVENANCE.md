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
