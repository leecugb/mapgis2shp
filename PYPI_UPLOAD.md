# Publishing mapgis2shp to PyPI

This package is published to PyPI under the distribution name **`mapgis2shp`**
because the name `pymapgis` is already taken.

The import name remains `pymapgis`:

```python
from pymapgis import Reader
```

## Prerequisites

- A [PyPI](https://pypi.org) account
- An API token from https://pypi.org/manage/account/token/

## Quick upload

1. Make sure you are in the repository root.
2. Set the token as environment variables:

   ```bash
   export TWINE_USERNAME=__token__
   export TWINE_PASSWORD=paste-your-pypi-token-here
   ```

3. Run the helper script:

   ```bash
   bash publish.sh
   ```

The script will:

- Run `twine check`
- Upload to **TestPyPI**
- Verify the package installs from TestPyPI
- Ask for confirmation before uploading to production **PyPI**

## Manual upload

```bash
# TestPyPI
twine upload --repository testpypi dist/*

# Production PyPI
twine upload dist/*
```

## Build from scratch

If you need to rebuild the distributions:

```bash
python -m build
```

Artifacts will appear in `dist/`.

## Security notes

- Never commit `~/.pypirc` or API tokens to Git.
- `.pypirc` is already in `.gitignore`.
- Prefer environment variables over writing credentials to disk.
