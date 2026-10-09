# Turnitoff

If the user asked you to install, set up or "get" this repo, read INSTALL.md first and follow it. The user is not technical: don't hand them commands to run, and get their yes before changing anything.

If you are here to change the code:

- Tests: `python3 -m unittest discover -s tests`.
- Standard library only. Keep it that way. There is a test for network imports.
- The writing rule lives in `turnitoff/data/`. After editing it or `turnitoff/scanner.py`, run `python3 scripts/build_skill.py`. A test fails if `dist/turnitoff-skill.zip` is stale.
- No em dashes in the rule files. A test checks.
