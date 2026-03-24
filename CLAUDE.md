# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin** — a library of reusable skills that Claude agents can load on-demand across projects. Distributed via Git or npm.

## Repo structure

```
.claude-plugin/
└── plugin.json        # Claude Code plugin manifest
skills/
└── <skill-name>/
    ├── SKILL.md       # primary entrypoint — loaded when the skill is activated
    ├── README.md      # optional: human-readable overview and quick-start
    ├── skill.json     # optional: extended metadata (triggers, capabilities, tags)
    └── *.md           # companion documents, loaded on-demand
package.json           # npm package metadata (for distribution)
LICENSE
```

## Installing this plugin

```bash
# In Claude Code:
/plugin install https://github.com/thevgergroup/mad-skills

# Or point Claude Code at a local checkout:
claude --plugin-dir /path/to/mad-skills
```

## Plugin manifest (`.claude-plugin/plugin.json`)

```json
{
  "name": "plugin-name",
  "description": "One-line description",
  "version": "1.0.0",
  "author": { "name": "..." },
  "homepage": "...",
  "repository": "...",
  "license": "MIT"
}
```

Only `plugin.json` goes in `.claude-plugin/`. Skills, commands, agents, and hooks all live at the repo root level.

## `skill.json` fields (per-skill extended metadata)

| Field | Purpose |
|---|---|
| `name` | Unique identifier, matches the directory name |
| `version` | Semver |
| `description` | One-line description for discovery |
| `triggers` | Phrases that should activate this skill |
| `entrypoint` | The primary markdown file to load (typically `SKILL.md`) |
| `capabilities` | List of what this skill can do |
| `author` | Author/team |
| `tags` | Searchable labels |

### SKILL.md conventions

Each `SKILL.md` **must** have YAML frontmatter for Claude Code to discover and list the skill:

```yaml
---
name: skill-name                  # defaults to directory name if omitted
description: When and why to use this skill — Claude uses this for auto-discovery
user-invocable: true              # false to hide from the / menu
argument-hint: "[task description]"  # shown in autocomplete
---
```

Once installed, skills are invoked as `/mad-skills:skill-name` in Claude Code.

### Companion doc conventions

- Opens with an overview and a "companion documents" table mapping tasks to specific `.md` files
- Companion docs are loaded **on-demand** — do not load all of them upfront
- Includes hard constraints and permanent decisions prominently, before any how-to content
- Uses checklists for multi-step sequences where order or completeness matters
- Common errors and their fixes belong in SKILL.md, not scattered across companion docs

### Companion doc conventions

Companion `.md` files in the skill directory are supporting reference material, not standalone skills. They should not have frontmatter. Reference them from `SKILL.md` so Claude knows when to load them.

## Adding a new skill

1. Create `skills/<skill-name>/` directory
2. Write `SKILL.md` as the entrypoint — include overview, constraints, companion doc table, and the core procedural content
3. Add companion `.md` files for subtopics that are only relevant in specific contexts
4. Optionally add `skill.json` for extended metadata (triggers, capabilities, tags)
5. Add a `README.md` if the skill benefits from a human-readable quick-start
6. Bump the version in both `package.json` and `.claude-plugin/plugin.json`

## Content standards

- **Base content on real experience, not just docs.** Where official docs and reality diverge, the skill reflects reality.
- **Surface permanent/irreversible decisions first.** Readers should hit hard constraints before any how-to steps.
- **Companion docs are opt-in.** Keep SKILL.md focused; push subtopics to companion files.
- **Version the skill** when its structure significantly changes (not for minor content fixes).
