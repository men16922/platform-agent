"""Make must export engine-specific defaults without overriding other reviewers.

Exercise both the real Makefile and its reinstall snippet in a child process.
No harness loop, model call, network request, or workspace commit is executed.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('makefile', ['Makefile', 'scripts/overnight/Makefile.harness.snippet'])
@pytest.mark.parametrize('variables,arguments,common,claude', [
    ({}, [], '', 'claude-fable-5-1'),
    ({'ENGINE':'codex','CODEX_MODEL':'gpt-6-astra'}, [], '', 'claude-fable-5-1'),
    ({'ENGINE':'kiro'}, [], '', 'claude-fable-5-1'),
    ({'ENGINE':'claude','OVERNIGHT_CRITIC_ENGINE':'codex'}, [], '', 'claude-fable-5-1'),
    ({'CLAUDE_CRITIC_MODEL':'custom-claude-reviewer'}, [], '', 'custom-claude-reviewer'),
    ({'OVERNIGHT_CRITIC_MODEL':'environment-reviewer'}, ['OVERNIGHT_CRITIC_MODEL=explicit-reviewer'],
     'explicit-reviewer', 'claude-fable-5-1'),
])
def test_make_exports_reviewer_defaults_without_cross_engine_leak(
        tmp_path, makefile, variables, arguments, common, claude):
    probe = tmp_path / 'probe.py'
    probe.write_text('import json,os\nprint(json.dumps({k:os.environ.get(k) for k in '
                     '["OVERNIGHT_CRITIC_MODEL","CLAUDE_CRITIC_MODEL","CLAUDE_MODEL"]}))\n')
    environment = {k:v for k,v in os.environ.items() if not (
        k.startswith(('CLAUDE_', 'CODEX_', 'OVERNIGHT_', 'MAKE')) or k == 'ENGINE')}
    environment.update(variables)
    # A supplemental make target reads only the actual exported environment;
    # no copy of the runner's model-selection implementation can hide a leak.
    recipe = '.PHONY: measure_reviewer\nmeasure_reviewer:\n\t@' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(probe)) + '\n'
    result = subprocess.run(['make','-s','-f',makefile,'-f','-','measure_reviewer',*arguments],
                            cwd=ROOT, env=environment, input=recipe,
                            text=True, capture_output=True, check=True)
    assert json.loads(result.stdout) == {
        'OVERNIGHT_CRITIC_MODEL': common,
        'CLAUDE_CRITIC_MODEL': claude,
        'CLAUDE_MODEL': 'claude-sonnet-5',
    }
