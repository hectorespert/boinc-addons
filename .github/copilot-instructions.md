# GitHub Copilot instructions

This repository's architecture, contributor workflow, and command reference are
documented in [`CLAUDE.md`](../CLAUDE.md) (repo root) — read it first, it is the
canonical source for this section and is kept up to date; this file only adapts
it to Copilot's own conventions instead of repeating it.

Quick reference (see `CLAUDE.md` for the full explanation of each):

- Two independent Home Assistant add-ons, each self-contained: `boinc/` (runs the
  BOINC client, via a Python "operator" in `boinc/operator/`) and `boinctui/` (a
  `ttyd` + `boinctui` terminal UI). They're versioned and released independently.
- Operator unit tests: `cd boinc/operator && python -m unittest discover -s test -t test`
  (needs `pip install dict2xml`).
- Build/run an add-on locally: see [`boinc/DEVELOPMENT.md`](../boinc/DEVELOPMENT.md),
  or use the agent-facing driver at
  [`.claude/skills/run-boinc-addons/`](../.claude/skills/run-boinc-addons/SKILL.md)
  (also invokable here as the `/run-boinc-addons` prompt).
- Docs site: `pip install -r requirements.txt && mkdocs build --strict`.
- Lint mirrors CI (`.github/workflows/lint.yaml`): `yamllint .`,
  `hadolint boinc/Dockerfile` / `hadolint boinctui/Dockerfile`,
  `shellcheck -s bash` over each add-on directory.
- CI/CD is `workflow_call`-chained (`lint` → `operator` tests → changed-add-on
  detection → version check → matrix build); builds/releases are gated on which
  files changed, so bumping an add-on's `config.yaml` version is what triggers
  its release.
- `config.yaml`, directory names, and internal code say "addon"/"add-on"; docs
  (READMEs) use "app" for the user-facing name — keep that split.
