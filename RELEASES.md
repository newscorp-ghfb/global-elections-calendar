# Releases

Spec §11.5. Each release and each recovery pair is recorded here by hand, with the user's approval.

## Releases

| Version | Code SHA | `requirements.txt` SHA-256 | `requirements-dev.txt` SHA-256 | Extension ZIP SHA-256 | ZIP files | Destination | Date | Approved by |
|---|---|---|---|---|---|---|---|---|
| 2.0.0 | 85e57c94242e21b88dcb5ba4202883d668b63007 | 78c3251a31b1a2fd33fb5ae14a2a23e03d75781adeef046584ae7bb47ca11d1d | aa121cd39d124587e2d1d19e7a276bf1501f8d167ef02210d2ba8790e0a2b6c8 | 0a393bd69f5c945e309d7dfab29585b5fed644bf00f566a96ee1aef887d54f6e (Python 3.14.1, zlib 1.3.1.zlib-ng) | 31 | company Web Store listing; ZIP shared with Load-unpacked users | 2026-11-03 | Mogzauri14 |

## Recovery pairs

A recovery pair is a `main` commit and the SHA-256 of the `elections.json` blob at that commit
(`git show <commit>:elections.json`). `scripts/republish.py --from-commit <commit>` restores only
a pair recorded here or in that commit's `status.json`.

| Name | Commit | `elections.json` SHA-256 | Checked |
|---|---|---|---|
| pre-v2 | c357fa77b9d2ed4a1eaa7c071efeba84a366273b | 1bf3cf900fef08bdd95269b10f8d66afd35245a97b033da15e1159312d79bc52 | 2026-11-01, republish --check |
