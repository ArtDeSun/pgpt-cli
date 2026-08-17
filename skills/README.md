# pgpt-cli skills

Skills are Markdown system instructions that can be activated for a request or chat without changing Python code.

Built-in skills live in this directory. Personal skills live in `~/.config/pgpt/skills/` and override a built-in skill with the same filename.

A skill filename is its CLI name. Create a personal skill with:

```bash
pgpt skill-new my-skill
```

Then edit the printed file under `~/.config/pgpt/skills/`. For example, `code-review.md` is selected with:

```bash
pgpt ask --skill code-review "Review this implementation."
```

Inside interactive chat:

```text
/skill code-review
/skill off
```

Keep skills narrow, explicit, and reusable. Do not place secrets in skill files that are committed to this repository.
