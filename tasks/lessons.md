# Lessons Learned

_Updated as corrections are made during development._

## Environment

- **Always use `.venv/bin/python -m pytest`** to run tests. System `python` / `python3` does not have project dependencies. Don't try `python` or `python3` first — go straight to `.venv/bin/python`.
