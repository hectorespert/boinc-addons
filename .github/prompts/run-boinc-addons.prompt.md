---
mode: agent
description: Build, run, and smoke-test the boinc, boinctui and boincui Home Assistant add-ons via Docker.
---

Build, run, and verify the `boinc`, `boinctui` and `boincui` Home Assistant add-ons
using the driver already committed in this repo — don't reinvent these steps or
paraphrase them from the READMEs.

Run from the repo root:

```bash
./.claude/skills/run-boinc-addons/smoke.sh boinc      # build + smoke-test boinc
./.claude/skills/run-boinc-addons/smoke.sh boinctui    # build + smoke-test boinctui
./.claude/skills/run-boinc-addons/smoke.sh boincui     # build + smoke-test boincui
./.claude/skills/run-boinc-addons/smoke.sh all         # all three, in sequence
```

Exit code 0 means the image built and the running container was verified
end to end (`boinccmd` RPC for `boinc`, an HTTP request to `ttyd` for
`boinctui`, a log line for `boincui`); each subcommand cleans up its own
containers/volumes on success.

Before improvising anything by hand (manual `docker run`, curling `boinctui`,
`docker exec`ing `boinccmd`), read
[`.claude/skills/run-boinc-addons/SKILL.md`](../../.claude/skills/run-boinc-addons/SKILL.md)
— it documents the exact prerequisites, the human-path fallback, and gotchas
that aren't obvious from the Dockerfiles (e.g. `boinccmd` needs
`--workdir /data/boinc`, and `ttyd` needs an `X-Remote-User-Name` header or it
returns `407 Proxy Auth Required`). The driver script itself is at
`.claude/skills/run-boinc-addons/smoke.sh`.
