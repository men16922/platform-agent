"""Run cdk.json's actual TypeScript app without global tools or npm downloads.

Application packaging is deliberately disabled: this checks the declared CDK
entrypoint and assembly, not pip/Docker bundling or deployed AWS resources.
"""
import json
from pathlib import Path
import shlex
import shutil
import subprocess

from tests._ts_toolchain import require_ts_toolchain


ROOT = Path(__file__).resolve().parents[1]
STACKS = ROOT / 'src/stacks'


def test_default_cdk_app_runs_with_only_project_dependencies(tmp_path):
    require_ts_toolchain(STACKS / 'node_modules/.bin/tsc', shutil.which('node') is not None,
                         'Run npm ci in src/stacks to validate the CDK app')
    project = tmp_path / 'project'
    stacks = project / 'src/stacks'
    stacks.mkdir(parents=True)
    for name in ('package.json', 'cdk.json', 'tsconfig.json', 'incident_agent_stack.ts'):
        shutil.copyfile(STACKS / name, stacks / name)
    (stacks / 'bin').mkdir()
    shutil.copyfile(STACKS / 'bin/app.ts', stacks / 'bin/app.ts')
    shutil.copytree(ROOT / 'src/step_functions', project / 'src/step_functions')
    (stacks / 'node_modules').symlink_to(STACKS / 'node_modules', target_is_directory=True)
    # Restrict executable search to Node/npm and the command shell. A global ts-node
    # or a prior npx download must not satisfy the missing project dependency.
    tools = tmp_path / 'tools'
    tools.mkdir()
    for name in ('node', 'npm', 'npx', 'sh'):
        executable = shutil.which(name)
        assert executable, f'{name} is required for the configured CDK app'
        (tools / name).symlink_to(Path(executable).resolve())
    config = json.loads((stacks / 'cdk.json').read_text())
    context = {**config.get('context', {}), 'aws:cdk:bundling-stacks': []}
    assembly = tmp_path / 'assembly'
    env = {
        'PATH': str(tools), 'HOME': str(tmp_path / 'home'),
        'npm_config_cache': str(tmp_path / 'npm-cache'), 'npm_config_offline': 'true',
        'AWS_EC2_METADATA_DISABLED': 'true',
        'CDK_DEFAULT_ACCOUNT': '111111111111', 'CDK_DEFAULT_REGION': 'ap-northeast-2',
        'CDK_OUTDIR': str(assembly), 'CDK_CONTEXT_JSON': json.dumps(context),
    }
    result = subprocess.run(shlex.split(config['app']), cwd=stacks, env=env,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((assembly / 'manifest.json').read_text())
    artifact = manifest['artifacts']['IncidentAgentStack']
    assert artifact['type'] == 'aws:cloudformation:stack'
    assert artifact['environment'] == 'aws://111111111111/ap-northeast-2'
    template = json.loads((assembly / artifact['properties']['templateFile']).read_text())
    kinds = {resource['Type'] for resource in template['Resources'].values()}
    assert {'AWS::StepFunctions::StateMachine', 'AWS::Lambda::Function',
            'AWS::DynamoDB::Table', 'AWS::Events::Rule'} <= kinds
