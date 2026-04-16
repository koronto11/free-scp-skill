# Advanced Skill Patterns

Reusable patterns for building powerful, well-structured Agent Skills.

## 1. Dynamic context injection

Inject live data into the skill prompt before the model sees it.

### Inline command
```markdown
---
name: pr-summary
description: Summarize the current pull request
---

## PR context
- Title: !`gh pr view --json title -q .title`
- Author: !`gh pr view --json author -q .author.login`
- Changed files: !`gh pr diff --name-only`
```

### Multi-line command block
````markdown
## Environment
```!
node --version
npm --version
git status --short
```
````

**Best practices:**
- Keep commands fast (< 2 seconds)
- Ensure commands are non-interactive
- Handle the case where the command is unavailable (the agent sees the stderr)

## 2. Subagent skills (`context: fork`)

Run the skill in an isolated context. The skill content becomes the subagent's prompt.

```yaml
---
name: deep-research
description: Research a topic thoroughly in the codebase
context: fork
agent: Explore
---

Research $ARGUMENTS thoroughly:

1. Find relevant files using Glob and Grep
2. Read and analyze the code
3. Summarize findings with specific file references
```

**When to use:**
- Large research tasks that would clutter the main conversation
- Tasks requiring many read/search operations
- Isolated validation or planning steps

**Warning:** Only use `context: fork` for skills with explicit tasks. Background guidelines without a task will cause the subagent to return without meaningful output.

## 3. Bundled scripts

Move reusable logic into scripts the skill executes.

### Example structure
```
my-skill/
├── SKILL.md
└── scripts/
    └── analyze.py
```

### SKILL.md reference
````markdown
Run the analysis script:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/analyze.py "$ARGUMENTS"
```
````

**Best practices:**
- Use `${CLAUDE_SKILL_DIR}` to reference the skill directory regardless of CWD
- Prefer Python with standard library for portability
- Include clear error messages and handle edge cases
- Document dependencies in the `compatibility` field

## 4. Validation loops

Instruct the agent to validate its own work before declaring success.

```markdown
## Editing workflow

1. Make your edits
2. Run validation: `python scripts/validate.py output/`
3. If validation fails:
   - Review the error message
   - Fix the issues
   - Run validation again
4. Only proceed when validation passes
```

This pattern dramatically reduces error rates for structured output tasks.

## 5. Plan-validate-execute

For batch or destructive operations, create an intermediate plan, validate it, then execute.

```markdown
## Database migration workflow

1. Analyze schema changes needed
2. Write `plan.json` describing every migration step
3. Validate: `python scripts/validate_plan.py plan.json`
4. If validation fails, revise `plan.json` and re-validate
5. Execute: `python scripts/execute_plan.py plan.json`
```

The validation step gives the agent specific, actionable feedback to self-correct.

## 6. Template-driven output

Provide a concrete template so the agent pattern-matches the desired output format.

````markdown
## Report structure

Use this template, adapting sections as needed:

```markdown
# [Analysis Title]

## Executive summary
[One-paragraph overview of key findings]

## Key findings
- Finding 1 with supporting data
- Finding 2 with supporting data

## Recommendations
1. Specific actionable recommendation
2. Specific actionable recommendation
```
````

Store long templates in `assets/` and reference them:

```markdown
For the full report template, see [assets/report-template.md](assets/report-template.md).
```

## 7. Checklists for multi-step workflows

Explicit checklists help agents track progress and avoid skipping steps.

```markdown
## Deployment checklist

- [ ] Run the test suite
- [ ] Build the application
- [ ] Push to the deployment target
- [ ] Verify the deployment succeeded
- [ ] Notify the team in #deployments
```

## 8. Gotchas sections

The highest-value content is often a list of environment-specific corrections.

```markdown
## Gotchas

- The `users` table uses soft deletes. Queries must include `WHERE deleted_at IS NULL`.
- The user ID is `user_id` in the DB, `uid` in auth, and `accountId` in billing.
- The `/health` endpoint returns 200 even if the DB is down. Use `/ready` instead.
```

Keep gotchas in `SKILL.md` where the agent reads them proactively.

## 9. Progressive reference loading

Tell the agent *when* to load reference files, not just that they exist.

```markdown
## Additional resources

- For complete API details, see [references/api-reference.md](references/api-reference.md)
- For error handling specifics, see [references/errors.md](references/errors.md)
- For output examples, see [references/examples.md](references/examples.md)

Load the relevant reference file before proceeding with that aspect of the task.
```

## 10. Argument-driven skills

Use argument substitution to make skills reusable.

```yaml
---
name: fix-issue
description: Fix a GitHub issue by number
disable-model-invocation: true
---

Fix GitHub issue $ARGUMENTS following our coding standards.

1. Read the issue description
2. Understand the requirements
3. Implement the fix
4. Write tests
5. Create a commit
```

Usage: `/fix-issue 123`

For multiple arguments:
```markdown
Migrate the $0 component from $1 to $2.
```

Usage: `/migrate-component SearchBar React Vue`

## 11. Permission pre-approval

Use `allowed-tools` to streamline tool execution for trusted skills.

```yaml
---
name: commit
description: Stage and commit the current changes
disable-model-invocation: true
allowed-tools: Bash(git add *) Bash(git commit *) Bash(git status *)
---

Create a commit with the message: $ARGUMENTS

1. Stage all changes: `git add -A`
2. Create commit: `git commit -m "$ARGUMENTS"`
```

## 12. Path-scoped skills

Limit auto-activation to specific file patterns.

```yaml
---
name: frontend-conventions
description: Frontend coding conventions for this project
paths:
  - "src/frontend/**/*"
  - "*.tsx"
  - "*.css"
---

When editing frontend code...
```

This prevents the skill from loading when working on unrelated parts of the codebase.

## 13. Background knowledge skills

For skills that provide context but shouldn't be invoked manually:

```yaml
---
name: legacy-system-context
description: Context about the legacy billing system
user-invocable: false
---

When working with files in `legacy/billing/`:
- The system uses SOAP, not REST
- Authentication is via HMAC, not JWT
- ...
```

## 14. Converting a CLAUDE.md section to a skill

When a `CLAUDE.md` section becomes a repeatable procedure:

1. Identify the procedural content (steps, checklists, commands)
2. Create a skill with a clear `name` and `description`
3. Move the procedure into `SKILL.md`
4. Leave static facts in `CLAUDE.md`
5. Add `disable-model-invocation: true` if the procedure has side effects

Example:
- `CLAUDE.md`: "We use Conventional Commits." (keep this)
- Skill `/commit`: Step-by-step commit workflow with message formatting. (extract this)
