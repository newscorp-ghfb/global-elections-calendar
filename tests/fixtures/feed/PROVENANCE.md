# Feed fixtures

## 2026-10-16-ff30417.json

The v1 `elections.json` as committed at `ff30417`: 27,557 bytes, `generated_at`
`2026-10-16T00:02:31Z`, no `published_at` and no `content_id`. It is the feed that the repository
serves before the first v2 publication, so the status tests use it as the "serving" bytes.

Command (from the repository root):

```
git show ff30417:elections.json > tests/fixtures/feed/2026-10-16-ff30417.json
```

SHA-256: `0e5ca8d5bf1cc90beb2a00081308e5cf2c81220eda2c3d3b2429ee715afef89b`

`.gitattributes` keeps `tests/fixtures/**` byte-exact (`-text`).
