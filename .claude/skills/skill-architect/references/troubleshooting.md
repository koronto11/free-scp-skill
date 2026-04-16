# Troubleshooting Guide for Agent Skills

Symptom-based diagnosis and fixes for common skill problems.

## Skill does not appear in the skills list

### Symptoms
- `/skills` (or platform equivalent) does not show the skill
- The agent acts as if the skill does not exist

### Causes & fixes

1. **Wrong directory path**
   - **Fix:** Verify the skill is in the correct platform-specific path (see `references/platforms.md`).
   - Claude Code: `.claude/skills/<name>/SKILL.md`
   - VS Code: `.agents/skills/<name>/SKILL.md`
   - Cursor: `.cursor/skills/<name>/SKILL.md`

2. **Directory name does not match `name` field**
   - **Fix:** The folder name and the `name` frontmatter field must match exactly.
   - Example: folder `code-review/` must have `name: code-review`

3. **Missing `SKILL.md` file**
   - **Fix:** The entrypoint file must be named exactly `SKILL.md` (case-sensitive on most platforms).

4. **Session started before skill was created**
   - **Fix:** In Claude Code, live change detection handles most edits, but creating a *new top-level* skills directory may require restarting the session.

5. **Frontmatter syntax error**
   - **Fix:** Ensure the frontmatter is wrapped in `---` markers and uses valid YAML. Common mistakes:
     - Tabs instead of spaces in YAML
     - Missing `---` at the top
     - Extra colons or unquoted strings that confuse the parser

## Skill does not trigger automatically

### Symptoms
- The agent answers without loading the skill
- The skill must be invoked manually with `/skill-name`

### Causes & fixes

1. **Description is too vague or generic**
   - **Fix:** Include specific keywords the user would naturally say. The description must describe both *what* the skill does and *when* to use it.
   - Good: `description: Generate database migrations from entity definitions. Use when the user asks to create a migration, schema change, or table update.`
   - Poor: `description: Handles database tasks.`

2. **`disable-model-invocation: true` is set**
   - **Fix:** Remove this field if you want the agent to auto-trigger the skill, or keep it and invoke manually.

3. **Description exceeded context budget**
   - **Fix:** In Claude Code, skill descriptions share a character budget (~1% of context window, fallback 8,000 chars). If you have many skills, descriptions may be truncated. Front-load the key use case in the first sentence.
   - You can raise the budget via `SLASH_COMMAND_TOOL_CHAR_BUDGET` env var.

4. **User request does not match description keywords**
   - **Fix:** Test with phrasing that closely matches the description. If users ask "deploy now" and the description says "release to production," add synonyms or use `when_to_use` (Claude Code) to broaden triggers.

5. **Paths restriction preventing activation**
   - **Fix:** If the skill has a `paths` frontmatter field, it only auto-activates when working with matching files. Verify your current file matches the glob.

## Skill triggers too often

### Symptoms
- The agent loads the skill for unrelated questions
- False positives waste context

### Causes & fixes

1. **Description is too broad**
   - **Fix:** Narrow the description to specific tasks and trigger phrases.
   - Instead of `description: Helps with code`, use `description: Refactors React class components to function components with hooks. Use when converting class components.`

2. **Missing `disable-model-invocation: true` for side-effect skills**
   - **Fix:** Any skill that deploys, commits, sends messages, or runs destructive commands should have `disable-model-invocation: true`.

3. **`when_to_use` is overly broad**
   - **Fix:** In Claude Code, `when_to_use` appends to the description. Keep it specific.

## Skill loads but behavior is wrong

### Symptoms
- The skill activates, but the agent does not follow the instructions correctly
- Output format is ignored
- Agent skips steps

### Causes & fixes

1. **Instructions are too vague**
   - **Fix:** Be prescriptive for fragile operations. Use exact commands, templates, and numbered steps.
   - Add a **Gotchas** section for non-obvious edge cases.

2. **Skill is too long**
   - **Fix:** If `SKILL.md` exceeds ~5,000 tokens, the agent may struggle to retain all instructions after context compaction. Move detailed reference material to separate files and tell the agent exactly when to read them.

3. **Instructions conflict with other active skills or system context**
   - **Fix:** Review other active skills. If two skills give contradictory guidance, the agent may behave unpredictably. Scope each skill tightly.

4. **Agent lost skill after context compaction**
   - **Fix:** In Claude Code, invoked skills are carried forward with a budget of 25,000 tokens shared across all re-attached skills. If many skills were invoked, older ones may be dropped. Re-invoke the skill if it stops influencing behavior.

5. **Missing template for output format**
   - **Fix:** Agents pattern-match well against concrete structures. Provide a template in a code block showing exactly what the output should look like.

## Shell command injection fails

### Symptoms
- `!`command` ` outputs nothing or an error
- Dynamic context is missing

### Causes & fixes

1. **Command not available in environment**
   - **Fix:** The command runs in the user's shell before the skill is sent to the model. Ensure the command exists in the PATH.

2. **`disableSkillShellExecution` is enabled**
   - **Fix:** In Claude Code, users can set `"disableSkillShellExecution": true` in settings to block all shell injection for safety. The skill cannot override this.

3. **Command is slow or interactive**
   - **Fix:** Shell injection commands should be fast and non-interactive. Avoid commands that prompt for input or take longer than a few seconds.

## File references are broken

### Symptoms
- The agent cannot find `references/FOO.md` or `scripts/bar.py`
- "File not found" errors when the skill runs

### Causes & fixes

1. **Wrong relative path**
   - **Fix:** Paths must be relative to the skill root (where `SKILL.md` lives).
   - If `SKILL.md` is at `.claude/skills/my-skill/SKILL.md`, then `references/guide.md` resolves to `.claude/skills/my-skill/references/guide.md`.

2. **Case sensitivity mismatch**
   - **Fix:** Ensure the referenced filename matches exactly, including case.

3. **File is outside the skill directory**
   - **Fix:** Reference files should live inside the skill directory. Use `assets/` or `references/` for external resources rather than absolute paths.

## Scripts fail when executed

### Symptoms
- `scripts/helper.py` throws errors
- Permission denied on shell scripts

### Causes & fixes

1. **Missing dependencies**
   - **Fix:** Document requirements in the `compatibility` field. For Python, prefer the standard library. If external packages are required, provide a `requirements.txt` and instructions to install it.

2. **Script lacks execute permission**
   - **Fix:** Ensure shell scripts have `chmod +x` set, or invoke them explicitly (`bash scripts/helper.sh`).

3. **Wrong interpreter path**
   - **Fix:** Use portable shebangs like `#!/usr/bin/env python3` or `#!/usr/bin/env bash`.

4. **Windows compatibility issue**
   - **Fix:** If the target audience includes Windows, write Python scripts (more portable) or provide PowerShell alternatives. Set `shell: powershell` in frontmatter for PowerShell blocks in Claude Code.

## Validation checklist for any broken skill

Run through this checklist before declaring a skill broken:

- [ ] Directory name == `name` field
- [ ] `SKILL.md` exists and is valid YAML + markdown
- [ ] `description` is specific and includes trigger keywords
- [ ] No frontmatter syntax errors (spaces, not tabs)
- [ ] Skill is in the correct platform discovery path
- [ ] File references use relative paths from the skill root
- [ ] Supporting files actually exist
- [ ] If using shell injection, the command is available and fast
- [ ] If using `disable-model-invocation: true`, you are invoking manually
- [ ] If using `paths`, the current file matches the glob
