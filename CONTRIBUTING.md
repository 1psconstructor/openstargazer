# Contributing to openstargazer

Thank you for your interest in contributing!

## Licensing of contributions — please read before you write code

openstargazer is **GPL-3.0-or-later**, and every contribution is published
under that licence. Nothing you send becomes less free, and you keep your
copyright: there is no assignment here and you are never asked for one.

On top of that, by opening a pull request or otherwise submitting a change
you grant the maintainer (1psconstructor) a **perpetual, worldwide,
non-exclusive, irrevocable, royalty-free and sublicensable licence to use,
reproduce, modify, prepare derivative works of, publicly perform, publicly
display and distribute your contribution — in source and in binary form,
alone or as part of a larger work — under any licence terms, including
proprietary and commercial ones.**

The same grant covers any patent claims you own or control that your
contribution would otherwise infringe, to the extent needed to make, use,
sell and distribute it as part of this project or a work derived from it.

**This grant is exercisable without asking you first.** No further
permission, notification, accounting or compensation is required, and the
grant survives you withdrawing from the project. That is the whole point of
recording it here rather than trying to collect agreements later, and it is
stated plainly so nobody can say they were surprised by it.

Here is what it does and does not mean:

- **It does not take anything away from you or from anyone else.** Your
  contribution remains available to everybody under GPL-3.0-or-later,
  permanently. This grant cannot undo that, and it grants you the same
  right to keep using your own work however you like — it is
  non-exclusive.
- **It does not make your work proprietary.** It lets the maintainer
  *additionally* ship the same code under different terms.
- **What it is for:** a paid edition alongside the free one is being
  considered, and the maintainer needs to be able to decide that on his
  own. Without this grant it becomes impossible the moment the first
  outside contribution is merged, because a GPL-only codebase with several
  copyright holders can only be relicensed if every single one of them
  agrees — including the ones nobody can reach in five years. Asking once,
  up front, is the honest version of that; asking afterwards is how
  projects end up stuck for good.
- **If you are not comfortable with it**, say so in the issue or PR. A
  change can often be taken as a bug report or a described approach rather
  than as patched code, and that route is genuinely welcome — it just
  cannot be taken as a patch.

Contributions are accepted only under these terms. A pull request that
declines them cannot be merged, however good it is.

### Sign your commits

Certify that you wrote the contribution, or otherwise have the right to
submit it under these terms, with a sign-off line:

```bash
git commit -s -m "..."
```

This appends `Signed-off-by: Your Name <your@email>` and means you agree to
the [Developer Certificate of Origin 1.1](https://developercertificate.org/)
and to the grant above. Use a real name and a reachable address.

### Third-party code, data and model weights

Do not bring in code, datasets or neural-network weights whose terms are
non-commercial, research-only, or simply unclear — and say where anything
external came from. This is not boilerplate: the head-pose weights this
project ships were trained from scratch specifically because the obvious
third-party ones carry non-commercial training data, and a single file with
a `CC BY-NC` lineage undoes that for the whole release. If you are unsure
about a licence, ask in the issue before writing the code.

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

## How this repository is published

`master` here is a **published snapshot**, not a working branch. It is
generated from the development history, which is why it arrives as whole
releases rather than as a stream of commits, and why it carries no inline
comments.

That has one consequence worth knowing before you spend an evening on a
patch: **a pull request cannot be merged into `master` as a merge.** The
next release would overwrite it. What happens instead is that your change
is applied to the development branch with your authorship kept, and it
appears in the following release. So the work is not wasted — but it will
not show up as a merged PR, and it may take until the next release to
become visible.

If that matters to you, open an issue first and say what you plan to
change. It is also simply the faster route for anything larger.

## Fork Workflow

1. Fork the repository on GitHub
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run `pytest tests/ -v` and ensure all tests pass
5. Commit with a clear message: `git commit -m "Add feature: ..."`
6. Push to your fork: `git push origin feature/my-feature`
7. Open a Pull Request against `master`, or an issue if you would rather
   discuss it first

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
