"""Execute the CDK Docker bundling command against real local files and pip."""
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('missing', ['requirements', 'agents', 'step_functions', 'init', None])
def test_docker_bundling_propagates_required_input_failures(tmp_path, missing):
    source = tmp_path / 'input'
    output = tmp_path / 'output'
    source.mkdir(); output.mkdir()
    if missing != 'requirements':
        # Empty requirements keep real pip offline; dependency installation is
        # separately verified in the Linux ARM64 Lambda runtime image.
        (source / 'requirements-lambda.txt').write_text('')
    (source / 'src').mkdir()
    for name in ('agents', 'step_functions'):
        if missing != name:
            directory = source / 'src' / name
            directory.mkdir()
            (directory / 'fixture.txt').write_text(name)
    if missing != 'init':
        (source / 'src/__init__.py').write_text('# package marker\n')
    # Read the actual command configured on the production asset, then execute
    # it. Asserting that the source merely contains "&&" missed this shell bug.
    text = (ROOT / 'src/stacks/incident_agent_stack.ts').read_text()
    commands = re.findall(r"^\s*command: \['bash', '-c', '([^']+)'\],$", text, re.MULTILINE)
    assert len(commands) == 1, 'Update the executable fixture if CDK bundling moves'
    command = commands[0].replace('/asset-input', str(source)).replace('/asset-output', str(output))
    toolbin = tmp_path / 'tools'
    toolbin.mkdir()
    # Use the test interpreter's real pip, not whichever unrelated venv happens
    # to supply a pip executable in the developer's shell.
    pip = toolbin / 'pip'
    pip.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' -m pip "$@"\n')
    pip.chmod(0o755)
    result = subprocess.run(['bash', '-c', command], text=True, capture_output=True,
                            timeout=30, env={**os.environ, 'PATH': str(toolbin) + os.pathsep + os.environ['PATH'],
                                             'PIP_NO_INDEX': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
                                             'PIP_CONFIG_FILE': os.devnull})
    if missing in ('requirements', 'agents', 'step_functions'):
        assert result.returncode != 0, result.stdout + result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        for name in ('agents', 'step_functions'):
            assert (output / 'src' / name / 'fixture.txt').read_text() == name
        assert (output / 'src/__init__.py').exists() == (missing != 'init')
