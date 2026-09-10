---
name: git-guardrails-opencode
description: Configure OpenCode permissions to block dangerous git commands such as push, reset --hard, clean, and branch -D. Use when user wants to prevent destructive git operations or add git safety guardrails.
---

# Setup Git Guardrails

Configure OpenCode's `permission.bash` policy to block dangerous Git commands before they run. This replaces command hooks and applies to every project that inherits the chosen config.

## What Gets Blocked

- `git push` (all variants including `--force`)
- `git reset --hard`
- `git clean -f` / `git clean -fd`
- `git branch -D`
- `git checkout .` / `git restore .`

## Steps

### 1. Ask scope

Ask whether to protect this project (`.opencode/opencode.json`) or all projects (`~/.config/opencode/opencode.jsonc`).

### 2. Add the permission policy

Merge this into the selected OpenCode configuration:

```jsonc
{
  "permission": {
    "bash": {
      "*": "ask",
      "git push*": "deny",
      "git reset --hard*": "deny",
      "git clean -f*": "deny",
      "git branch -D*": "deny",
      "git checkout .": "deny",
      "git restore .": "deny"
    }
  }
}
```

Rule order matters: OpenCode uses the last matching rule, so the broad `*` rule must come first.

### 3. Verify

Start a new OpenCode session and request one of the blocked commands. OpenCode should deny it before the shell runs.

Quit and restart OpenCode after changing its configuration.
