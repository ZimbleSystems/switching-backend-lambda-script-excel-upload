#!/usr/bin/env bash
# Build the Lambda deployment zip with **Linux** wheels.
#
# Doing `pip install` on Windows produces Windows wheels (numpy/pandas
# have a `os.add_dll_directory` call that doesn't exist on Linux).
# Lambda runs on Linux, so we install dependencies inside a Linux
# python:3.11-slim container instead. The /var/task layout is the
# same as what AWS Lambda expects.
#
# Clean, pip, copy, strip, and zip all run **inside Docker** so WSL/Git
# Bash on /mnt/c/... are not blocked by root-owned files from prior runs.
#
# Works in Git Bash on Windows, WSL, and macOS/Linux.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
BUILD="$HERE/build"

# Docker volume mounts on Windows need Windows-style paths
if command -v cygpath >/dev/null 2>&1; then
  ROOT_FOR_DOCKER="$(cygpath -m "$ROOT")"
  BUILD_FOR_DOCKER="$(cygpath -m "$BUILD")"
else
  ROOT_FOR_DOCKER="$ROOT"
  BUILD_FOR_DOCKER="$BUILD"
fi

mkdir -p "$BUILD"

echo ">> Building package.zip inside Docker (python:3.11-slim) ..."
# MSYS_NO_PATHCONV=1 prevents Git Bash from rewriting /work, /build, /work/...
# The leading // on -w is also a MINGW workaround so the path is left alone.
MSYS_NO_PATHCONV=1 \
docker run --rm \
  -v "$ROOT_FOR_DOCKER:/work:ro" \
  -v "$BUILD_FOR_DOCKER:/build" \
  -w //work \
  python:3.11-slim \
  sh -ec '
    set -e
    rm -rf /build/* 2>/dev/null || true
    pip install --upgrade pip --quiet --root-user-action=ignore
    pip install -r /work/requirements.txt -t /build --quiet --root-user-action=ignore
    cp -r /work/src /build/src
    cp /work/lambda_function.py /build/lambda_function.py
    find /build -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
    find /build -type d -name tests -prune -exec rm -rf {} + 2>/dev/null || true
    find /build -type d -name test -prune -exec rm -rf {} + 2>/dev/null || true
    cd /build
    python -c "
import os, shutil
shutil.make_archive(\"package\", \"zip\", \".\")
print(\"package.zip size:\", os.path.getsize(\"package.zip\"), \"bytes\")
"
  '

echo ">> Done: $BUILD/package.zip"
