# Contributing to DevShowcase

Thanks for your interest in contributing! This guide will help you get started.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/<your-username>/devshowcase.git`
3. **Create a branch**: `git checkout -b feature/your-feature`
4. **Set up** the development environment (see [README.md](README.md#local-development))

## Development Workflow

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Fill in required API keys
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Fill in OAuth credentials
npm run dev
```

### Running Tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -v
```

All 122 tests use mocks — no API keys needed to run the test suite.

## Code Standards

- **Python 3.12+** with type annotations on all function signatures
- **Module size**: Maximum 500 lines per file
- **Simplicity first**: Make every change as simple as possible
- **Minimal impact**: Only touch what's necessary

## Pull Request Guidelines

1. **One concern per PR** — keep changes focused
2. **Write tests** for new functionality
3. **Run the full test suite** before submitting
4. **Describe your changes** — explain *why*, not just *what*
5. **Link related issues** in the PR description

## Reporting Bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) and include:
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, Node version)

## Suggesting Features

Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md) and describe:
- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
