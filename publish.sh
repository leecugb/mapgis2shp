#!/usr/bin/env bash
# Convenience script to publish pymapgis-reader to TestPyPI and PyPI.
#
# Usage:
#   export TWINE_USERNAME=__token__
#   export TWINE_PASSWORD=pypi-AgEIc...
#   ./publish.sh
#
# The script will first upload to TestPyPI, verify the package can be installed,
# and then prompt before uploading to the production PyPI index.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

DIST_DIR="${SCRIPT_DIR}/dist"

# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------

if [[ -z "${TWINE_USERNAME:-}" || -z "${TWINE_PASSWORD:-}" ]]; then
    echo "Error: TWINE_USERNAME and TWINE_PASSWORD must be set." >&2
    echo "For PyPI API tokens, set:" >&2
    echo "  export TWINE_USERNAME=__token__" >&2
    echo "  export TWINE_PASSWORD=pypi-..." >&2
    exit 1
fi

if [[ ! -d "${DIST_DIR}" ]]; then
    echo "Error: ${DIST_DIR} not found. Run 'python -m build' first." >&2
    exit 1
fi

if ! compgen -G "${DIST_DIR}/*" > /dev/null; then
    echo "Error: ${DIST_DIR} is empty. Run 'python -m build' first." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------

echo "==> Running twine check..."
twine check "${DIST_DIR}"/*

echo "==> Built artifacts:"
ls -1 "${DIST_DIR}"/*

# ---------------------------------------------------------------------------
# TestPyPI upload + install verification
# ---------------------------------------------------------------------------

echo ""
echo "==> Uploading to TestPyPI..."
twine upload --repository testpypi "${DIST_DIR}"/*

echo ""
echo "==> Waiting for TestPyPI index to update..."
sleep 15

echo ""
echo "==> Verifying install from TestPyPI..."
TEST_VENV="$(mktemp -d)"
python -m venv "${TEST_VENV}"
"${TEST_VENV}/bin/pip" install --quiet --index-url https://test.pypi.org/simple/ mapgis2shp
"${TEST_VENV}/bin/python" -c "from pymapgis import Reader; print('TestPyPI install OK:', Reader.__module__)"
rm -rf "${TEST_VENV}"

# ---------------------------------------------------------------------------
# Production PyPI upload
# ---------------------------------------------------------------------------

echo ""
read -r -p "TestPyPI upload succeeded. Upload to production PyPI? [y/N] " confirm
if [[ "${confirm}" =~ ^[Yy]$ ]]; then
    echo ""
    echo "==> Uploading to PyPI..."
    twine upload "${DIST_DIR}"/*
    echo ""
    echo "Upload complete. Verify with:"
    echo "  pip install mapgis2shp"
else
    echo "Production upload cancelled."
    exit 0
fi
