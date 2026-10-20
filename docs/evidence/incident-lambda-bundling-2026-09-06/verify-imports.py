import importlib
import json
import platform
import sys
import yaml
assert yaml.__with_libyaml__
print("PyYAML native extension:",yaml.CLoader.__module__)
handlers=['src.agents.operations.aws.detector.lambda_handler', 'src.agents.operations.aws.analyzer.lambda_handler', 'src.agents.operations.aws.decision.lambda_handler', 'src.agents.operations.aws.approval_bridge.handler.lambda_handler', 'src.agents.operations.aws.runbook_seed.lambda_handler', 'src.agents.operations.aws.executor.lambda_handler', 'src.agents.provisioning.handler.lambda_handler', 'src.agents.provisioning.artifact_writer.lambda_handler', 'src.agents.deployment.handler.lambda_handler', 'src.agents.deployment.rollback_executor.lambda_handler', 'src.agents.ingress.handler.lambda_handler', 'src.agents.router.handler.lambda_handler', 'src.agents.operations.aws.reporting.lambda_handler']
results=[]
for name in handlers:
    module, attribute = name.rsplit('.',1)
    try:
        value=getattr(importlib.import_module(module), attribute)
        assert callable(value)
        results.append({'handler':name,'ok':True})
    except Exception as error:
        results.append({'handler':name,'ok':False,'error':type(error).__name__+': '+str(error)})
print(json.dumps({'python':sys.version,'machine':platform.machine(),'results':results},indent=2))
raise SystemExit(any(not x['ok'] for x in results))
