# Contributing

Small, testable fixes are welcome.

Before opening an issue or pull request:

- use synthetic or fully redacted fixtures;
- do not upload participant data or real audit reports;
- explain the file format and the expected release-review behaviour;
- add a regression test when changing a detector, reader or report decision;
- run `python -m unittest` and `git diff --check`.

Keep detection claims narrow. A passing test should show that one documented
case is handled correctly, not that an arbitrary dataset is anonymous or safe to
release.

For software vulnerabilities or potentially sensitive public-dataset findings,
follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
