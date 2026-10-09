# Turnitoff

Makes Claude and ChatGPT stop writing like an AI.
## Get it

Paste this to Claude or ChatGPT:

> Set up https://github.com/lucasjamesss/Turnitoff for me. Follow INSTALL.md in it. Don't make me do anything technical.

It asks you one yes or no question, then does the rest. How much it can do depends on the app.

| You use | What happens |
|---|---|
| Claude Code, or any Claude that can run commands on your computer | Fully automatic. Rule, checker and tool installed. Quit and reopen Claude after. |
| Claude.ai | Claude hands you a small file and three clicks to upload it, or a block to paste into settings. |
| ChatGPT | ChatGPT hands you a block to paste into Settings, Personalization. About 30 seconds. |

## Free ChatGPT or Claude? Paste this

Can't install anything? Copy this block into your AI's settings once. It applies to every chat after that.

```
Write like one specific person, not a template.

1. Answer or claim first. No intro, no recap, no "In conclusion".
2. Real specifics only: names, numbers, places, one example. If none were given, ask or leave [gap]. Never invent.
3. Vary rhythm hard. Mix 3-word and 30-word sentences. Never three similar-length sentences in a row. Uneven paragraphs. Fragments and contractions are fine.
4. Banned words: delve, tapestry, landscape, pivotal, crucial, underscore, showcase, foster, enhance, testament, intricate, multifaceted, holistic, robust, seamless, leverage, utilize, navigate, realm, journey, vibrant, "in today's", "it's worth noting", "when it comes to", Moreover, Furthermore, Additionally.
5. Banned shapes: "not just X, but Y" and "it's not X, it's Y" (say Y); rule-of-three lists by reflex; trailing ", highlighting/ensuring/underscoring..." clauses; closing summaries.
6. No em dashes. Commas or periods.
7. No bold-lead bullets, emoji, or headers on short pieces.
8. One hedge per claim. Say "I don't know" when true.
9. Fix a flagged sentence by rewriting it. Never swap in a synonym.
```

Where it goes:

- ChatGPT: Settings, Personalization, Custom instructions. Free and Go plans allow 1,500 characters. The block is about 1,100.
- Claude: Settings, Profile, personal preferences. Or paste it at the top of a chat.
- Any other AI: paste it at the start of the chat.

Menu names change. Look for the nearest setting that says custom instructions or preferences.

## What it does

Readers and detectors pick up the same things: stock AI vocabulary, the "not this, but that" construction, sentences that are all the same length, a tidy summary at the end. Turnitoff gives the AI a short rule that avoids them, plus a checker that flags what's left so the AI can rewrite it.

On Claude Code the checker runs by itself whenever Claude saves a text file. Everywhere else the rule is an instruction the AI can follow or ignore.

## What it does not do

- It can't promise a result in any detector. They are unreliable and flag human writing too, especially formal writing and non-native English. The checker's thresholds are uncalibrated guesses.
- It can't invent a voice. Give the AI real details (names, numbers, one true example) and a sample of your own writing.
- It doesn't change your school's or employer's rules on AI. Follow them.

## For the AI reading this

If a user sent you this link, read [INSTALL.md](INSTALL.md) and follow it. Raw copy: https://raw.githubusercontent.com/lucasjamesss/Turnitoff/main/INSTALL.md

If you can't change anything on their computer, or they use a free plan, don't stop there. Give them the block from the section above in a code box, unchanged. Tell them to paste it into their custom instructions or preferences, and tell them which setting that is for the app they use (the list above). If they use both ChatGPT and Claude, they need to do it in each.

## Manual install

You need Python 3.8 or newer.

    git clone https://github.com/lucasjamesss/Turnitoff.git
    python3 Turnitoff/install.py

Options: `--strict` also checks long chat replies and makes Claude rewrite flagged ones. `--dry-run` shows what would change. `--uninstall` removes everything.

Undo later with `python3 ~/.turnitoff/install.py --uninstall`.

## What the installer changes

- `~/.turnitoff/`: a copy of the program.
- `~/.claude/rules/turnitoff.md`: the writing rule. Claude Code loads it every session.
- `~/.claude/settings.json`: one hook that scans text files Claude writes. A backup is saved first as `settings.json.turnitoff-backup`.
- Claude Code and Claude Desktop: registers a small tool server (`scan_text`, `scan_file`, `get_rules`). Desktop's config gets the same backup treatment.

Standard library only. No network calls. No telemetry.

## Use it by hand

    python3 -m turnitoff scan draft.txt
    python3 -m turnitoff rules

Set `TURNITOFF=off` to pause the hook. Set `TURNITOFF_BLOCK_AT=8` to make it less strict (default 6).

Tests: `python3 -m unittest discover -s tests`. After editing the rule text or the scanner, run `python3 scripts/build_skill.py` to refresh the skill zip.

## License

MIT.
