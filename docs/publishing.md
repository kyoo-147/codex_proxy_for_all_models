# Publishing

## Build

```bash
python -m build
```

## Upload to PyPI

```bash
python -m twine upload dist/*
```

## Verify

```bash
pip install codex-proxy-for-all-models
codex-proxy
```
