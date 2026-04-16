# Cross-Platform Compatibility Reference

Agent Skills are an open standard. The `SKILL.md` format is consistent across platforms, but discovery paths and extended features vary. This reference helps you write skills that work everywhere.

## Platform discovery paths

| Platform | Skill discovery path | Notes |
|----------|---------------------|-------|
| **Claude Code** | `.claude/skills/<name>/` (project) <br> `~/.claude/skills/<name>/` (personal) | Also loads from `--add-dir` subdirectories and nested `.claude/skills/`. |
| **Claude (API/SDK)** | Varies by integration | Uses same open standard; deployment depends on the host app. |
| **VS Code** | `.agents/skills/<name>/` (project) <br> User settings path (global) | Copilot Chat agent mode discovers these automatically. |
| **GitHub Copilot** | Same as VS Code | Editor-agnostic path within the workspace. |
| **Cursor** | `.cursor/skills/<name>/` or `.cursor/rules/` | Check latest Cursor docs; also supports `.cursorrules` files. |
| **OpenAI Codex** | `.codex/skills/<name>/` | Codex CLI follows the open standard closely. |
| **Gemini CLI** | `.gemini/skills/<name>/` | Open-source; skills docs at geminicli.com. |
| **OpenCode** | `.opencode/skills/<name>/` | Terminal, IDE, and desktop support. |
| **OpenHands** | Configurable in settings | Open platform; see docs.openhands.dev. |
| **Goose** | `.goose/skills/<name>/` | Extensible agent from Block. |
| **Roo Code** | `.roo/skills/<name>/` | VS Code extension with deep project context. |
| **Kiro** | `.kiro/skills/<name>/` | Spec-driven development platform. |
| **Letta** | Varies by deployment | Stateful agents with memory. |
| **VT Code** | Configurable | Open-source coding agent. |
| **Mux** | Configurable | Parallel agents with isolated workspaces. |
| **Emdash** | Configurable | Provider-agnostic desktop app. |
| **Workshop** | Configurable | Desktop, web, and CLI. |
| **Autohand** | Configurable | ReAct-pattern terminal agent. |
| **Amp** | Configurable | Frontier coding agent. |
| **Command Code** | Configurable | Taste-learning coding agent. |
| **Piebald** | Configurable | Desktop & web app. |
| **Factory** | Configurable | AI-native software dev platform. |
| **Qodo** | Configurable | Agentic code integrity platform. |
| **Spring AI** | Configurable | Java-based AI framework. |
| **Databricks Genie Code** | Configurable | Data work optimized. |
| **Snowflake Cortex Code** | Configurable | Snowflake platform agent. |
| **Google AI Edge Gallery** | `.agents/skills/<name>/` or app-specific | Mobile LLM runner. |
| **nanobot** | Configurable | Ultra-lightweight personal AI agent. |
| **Mistral Vibe** | Configurable | CLI coding assistant. |
| **Trae** | Configurable | Adaptive AI IDE. |

## Writing portable skills

To maximize compatibility across all platforms:

### 1. Stick to the open standard frontmatter

Use only these fields for guaranteed portability:
- `name` (required)
- `description` (required)
- `license` (optional)
- `compatibility` (optional)
- `metadata` (optional)
- `allowed-tools` (optional)

Claude Code-specific fields (`disable-model-invocation`, `context`, `agent`, `model`, `effort`, `hooks`, `paths`, `shell`) are safe to include — other platforms will simply ignore unknown frontmatter fields.

### 2. Avoid platform-specific tool assumptions

Not every agent has the same tool set. If your skill references tools:
- Use generic descriptions where possible ("search the codebase" instead of "use Glob and Grep")
- In Claude Code, you can be explicit because Glob/Grep/Bash/Read/Edit/Write are available
- For other platforms, phrase instructions as capabilities rather than exact tool names

### 3. Script language portability

Scripts in `scripts/` should use languages commonly available:
- **Bash** — Universal on macOS/Linux; use with caution on Windows unless WSL is assumed
- **Python** — Widely available; stick to the standard library to avoid dependency issues
- **Node.js** — Good for JS/TS projects, but not guaranteed to be installed everywhere

If a script requires specific dependencies, document them in the `compatibility` field.

### 4. Path separators

When writing scripts or instructions that involve file paths:
- Use forward slashes (`/`) in skill instructions (markdown is platform-agnostic)
- In shell scripts, be mindful of Windows compatibility if the target audience includes Windows developers

### 5. Shell command syntax (`!` injection)

Dynamic context injection with `` !`command` `` and ` ```! ` blocks is a **Claude Code feature**. Other platforms may not support it. For maximum portability:
- Use it when the primary target is Claude Code
- Provide fallback instructions for platforms without shell injection

Example of a portable approach:
```markdown
## Current branch
If running in Claude Code, the branch info is injected below:
- Branch: !`git branch --show-current`

Otherwise, determine the current branch using available tools or ask the user.
```

### 6. Subagent instructions

`context: fork` and `agent: Explore/Plan` are Claude Code extensions. For cross-platform skills that use subagents:
- Consider this a Claude Code optimization
- The skill should still provide value on other platforms by falling back to inline execution

## Platform-specific notes

### Claude Code
- Supports `allowed-tools` for permission pre-approval
- Supports live change detection (edits to skill files take effect immediately)
- Supports nested skill discovery in monorepos
- Skill descriptions compete for a context budget (~1% of context window, fallback 8,000 chars)

### VS Code / GitHub Copilot
- Skills live under `.agents/skills/`
- Agent mode must be selected in Copilot Chat
- Tool availability depends on the VS Code extension implementation

### Cursor
- Cursor has its own rule system in addition to Agent Skills
- Skills may be placed in `.cursor/skills/` or referenced from `.cursorrules`
- Check Cursor's latest documentation for any format deviations

### OpenAI Codex
- Codex uses `.codex/skills/`
- Very close to the open standard; good portability target

### Gemini CLI
- Uses `.gemini/skills/`
- Open source and actively adopting the standard

## Compatibility frontmatter examples

Indicate portability expectations clearly:

```yaml
# Designed for Claude Code but safe elsewhere
compatibility: Optimized for Claude Code. Uses standard markdown instructions and should work in any Agent Skills-compatible client.
```

```yaml
# Requires specific platform features
compatibility: Requires Claude Code for dynamic shell injection (!`cmd`) and subagent forking. Core instructions are valid on any compatible platform.
```

```yaml
# Script dependency
compatibility: Requires Python 3.10+ for bundled scripts. Tested on Claude Code and VS Code Copilot.
```
