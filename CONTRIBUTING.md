# Contributing

## Development

Run tests:

```bash
python -m unittest discover -s tests -v
```

## Scope

Contributions should keep the project:

- lightweight
- stdlib-first
- vendor-agnostic
- focused on Codex compatibility

## Pull requests

- add tests for behavior changes
- avoid introducing framework dependencies without strong reason
- document new provider-specific quirks in `docs/providers.md`
