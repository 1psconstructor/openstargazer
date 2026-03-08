# Contributing to openstargazer

Thank you for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/1psconstructor/openstargazer.git
cd openstargazer
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,tray]"
```

## Running Tests

```bash
pytest tests/ -v
```

Tests run without physical hardware — the mock tracker is used automatically.

## Fork Workflow

1. Fork the repository on GitHub
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run `pytest tests/ -v` and ensure all tests pass
5. Commit with a clear message: `git commit -m "Add feature: ..."`
6. Push to your fork: `git push origin feature/my-feature`
7. Open a Pull Request against `main`

## Code Style

- Follow PEP 8
- Use type annotations for public functions
- Keep functions focused and short
- Prefer explicit imports over `import *`

## Reporting Issues

Use the [GitHub issue tracker](https://github.com/1psconstructor/openstargazer/issues).

For bug reports, include:
- Linux distribution and version
- Python version (`python3 --version`)
- Tobii ET5 USB PID (`lsusb | grep 2104`)
- Relevant log output (`journalctl --user -u openstargazer`)

## Pull Request Guidelines

- Reference any related issue in the PR description
- Include a brief description of what changed and why
- Keep PRs focused — one feature or fix per PR
- Add or update tests if the change affects testable behaviour
