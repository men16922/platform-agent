#!/usr/bin/env python3
"""Build an isolated Linux ARM64 Lambda asset in a new/empty output directory."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('registry', 'registry_write', 'registry_planner',
           'registry_authorization', 'registry_readers', 'registry_lambda',
           'registry_plan_store', 'registry_preview_service')


def build(output: Path):
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('output directory must be empty')
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
        '--platform', 'manylinux2014_aarch64', '--python-version', '3.13',
        '--implementation', 'cp', '--abi', 'cp313', '--only-binary=:all:',
        '--no-compile', '--target', str(output),
        '-r', str(ROOT / 'requirements-registry-planner.txt'),
    ], check=True, stderr=subprocess.STDOUT)
    package = output / 'src/agents/platform'
    package.mkdir(parents=True)
    # Namespace packages deliberately omit broad platform/__init__ exports:
    # no cluster/delivery adapters or unrelated agent code in this Lambda.
    for module in MODULES:
        shutil.copyfile(ROOT / f'src/agents/platform/{module}.py', package / f'{module}.py')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    try:
        output = parser.parse_args().output
        build(output)
        print(f'BUILT: {output.resolve()}')
    except Exception as error:
        print(f'FAILED: {error}')
        raise SystemExit(1)
