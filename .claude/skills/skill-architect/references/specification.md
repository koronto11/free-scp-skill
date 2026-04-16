# Agent Skills Specification Reference

Complete reference for the Agent Skills open standard (`agentskills.io`).

## Directory structure

A skill is a directory containing, at minimum, a `SKILL.md` file:

```
skill-name/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
├── assets/           # Optional: templates, resources
└── ...               # Any additional files or directories
```

## `SKILL.md` format

The file must contain YAML frontmatter followed by Markdown content.

### Frontmatter fields

| Field | Required | Constraints |
|-------|----------|-------------|
| `name` | Yes | 1-64 chars. Lowercase `a-z`, digits, hyphens only. No leading/trailing/consecutive hyphens. Must match parent directory name. |
| `description` | Yes | 1-1024 chars. Non-empty. Must state what the skill does AND when to use it. |
| `license` | No | License name or reference to bundled license file. Keep it short. |
| `compatibility` | No | Max 500 chars. Environment requirements: intended product, system packages, network access, etc. |
| `metadata` | No | Arbitrary key-value mapping (strings) for additional metadata. Use reasonably unique keys. |
| `allowed-tools` | No | Space-separated string of pre-approved tools. (Experimental; support varies by platform.) |

### Claude Code extended frontmatter

Claude Code supports additional fields beyond the open standard:

| Field | Purpose |
|-------|---------|
| `when_to_use` | Extra trigger context. Appended to `description` for the model. |
| `argument-hint` | Hint shown in autocomplete, e.g. `[issue-number]`. |
| `disable-model-invocation` | Set `true` to prevent automatic invocation. Use for side-effect workflows. |
| `user-invocable` | Set `false` to hide from the `/` menu. Use for background knowledge only. |
| `model` | Override model when this skill is active. |
| `effort` | Override effort level (`low`, `medium`, `high`, `max`). |
| `context` | Set `fork` to run in an isolated subagent context. |
| `agent` | Subagent type to use with `context: fork` (e.g., `Explore`, `Plan`). |
| `hooks` | Skill-scoped lifecycle hooks. |
| `paths` | Glob patterns limiting auto-activation to matching files. |
| `shell` | `bash` (default) or `powershell` for `!` commands. |

### Naming validation

**Valid:**
```yaml
name: pdf-processing
name: data-analysis
name: code-review
```

**Invalid:**
```yaml
name: PDF-Processing        # uppercase
name: -pdf                  # leading hyphen
name: pdf--processing       # consecutive hyphens
name: pdf_processing        # underscore (spec allows only hyphens)
```

### Description best practices

**Good:**
```yaml
description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.
```

**Poor:**
```yaml
description: Helps with PDFs.
```

## Progressive disclosure rules

1. **Metadata** (~100 tokens): `name` + `description` loaded at startup for all discovered skills.
2. **Instructions** (< 5,000 tokens recommended): Full `SKILL.md` body loaded only when activated.
3. **Resources** (as needed): Files in `scripts/`, `references/`, `assets/` loaded only when referenced.

Keep `SKILL.md` under 500 lines. Move detailed reference material to separate files.

## File references

Use relative paths from the skill root:

```markdown
See [the reference guide](references/REFERENCE.md) for details.

Run the extraction script:
scripts/extract.py
```

Keep references one level deep from `SKILL.md`. Avoid deeply nested chains.

## Dynamic context (Claude Code only)

Use `!`command` ` to inject shell command output before the skill is sent to the model:

```yaml
---
name: pr-summary
description: Summarize a pull request
---

## PR data
- Diff: !`gh pr diff`
- Files: !`gh pr diff --name-only`
```

For multi-line commands, use a fenced block opened with ` ```! `.

> This is preprocessing, not a tool call. The model only sees the command output.

## Argument substitution

| Variable | Meaning |
|----------|---------|
| `$ARGUMENTS` | All arguments as a single string |
| `$ARGUMENTS[N]` | Argument by 0-based index |
| `$N` | Shorthand for `$ARGUMENTS[N]` |
| `${CLAUDE_SESSION_ID}` | Current session ID |
| `${CLAUDE_SKILL_DIR}` | Directory containing the skill's `SKILL.md` |

Example:
```yaml
---
name: migrate-component
---

Migrate the $0 component from $1 to $2.
```

## Validation tools

Use the official `skills-ref` CLI to validate skills:

```bash
npx skills-ref validate ./my-skill
```

This checks frontmatter validity and naming conventions.
