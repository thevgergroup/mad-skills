<div align="center">
  <img src="logo.svg" width="120" alt="mad-skills logo"/>
  <h1>mad-skills</h1>
  <p><strong>Battle-tested Claude Code skills. Built from shipping real things, not reading docs.</strong></p>

  <p>
    <a href="https://github.com/thevgergroup/mad-skills/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"/></a>
    <a href="https://skills.sh"><img src="https://img.shields.io/badge/skills.sh-discoverable-00d4ff.svg" alt="skills.sh"/></a>
    <img src="https://img.shields.io/badge/Claude%20Code-plugin-orange.svg" alt="Claude Code Plugin"/>
  </p>
</div>

---

Each skill in this collection is grounded in direct shipping experience — where the official docs and reality diverge, these skills reflect reality.

## Install

**Via Claude Code plugin manager:**
```
/plugin install https://github.com/thevgergroup/mad-skills
```

**Via skills.sh — install a specific skill:**
```bash
npx skills add https://github.com/thevgergroup/mad-skills --skill aws-marketplace
```

**Or install all skills:**
```bash
npx skills add https://github.com/thevgergroup/mad-skills
```

Once installed, skills are available as `/mad-skills:<skill-name>` in Claude Code.

## Skills

| Skill | Description |
|---|---|
| [`aws-marketplace`](skills/aws-marketplace/) | Publish paid container products to AWS Marketplace — entity model, 14-step creation sequence, ECR pipeline, pricing, CloudFormation, review process, and post-launch operations |

## How these skills work

Each skill is a `SKILL.md` entrypoint with a table of companion documents that load on-demand based on the task. The core skill stays focused; detail lives in companion files that Claude pulls in only when relevant.

```
skills/<name>/
├── SKILL.md          # entrypoint — loaded when you invoke the skill
└── *.md              # companion docs, loaded on-demand per task
```

## Contributing

Skills that belong here:
- Grounded in real production experience, not just documentation summaries
- Cover the gaps and gotchas that official docs gloss over
- Include hard constraints and irreversible decisions prominently

To add a skill, open a PR with a new directory under `skills/`. See [CLAUDE.md](CLAUDE.md) for structure and conventions.

## License

MIT — [The Vger Group](https://github.com/thevgergroup)
