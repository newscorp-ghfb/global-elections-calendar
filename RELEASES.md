# Releases

Spec §11.5. Each release and each recovery pair is recorded here by hand, with the user's approval.

## Releases

| Version | Code SHA | `requirements.txt` SHA-256 | `requirements-dev.txt` SHA-256 | Extension ZIP SHA-256 | ZIP files | Destination | Date | Approved by |
|---|---|---|---|---|---|---|---|---|

## Recovery pairs

A recovery pair is a `main` commit and the SHA-256 of the `elections.json` blob at that commit
(`git show <commit>:elections.json`). `scripts/republish.py --from-commit <commit>` restores only
a pair recorded here or in that commit's `status.json`.

| Name | Commit | `elections.json` SHA-256 | Checked |
|---|---|---|---|
