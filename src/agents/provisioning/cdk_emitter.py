"""
Provisioning Agent — CDK TypeScript artifact emitter.

Turns a normalized provisioning blueprint plus IAM plan into a small,
reviewable CDK TypeScript project artifact that can later be committed,
packaged, or deployed by an external execution step.
"""

from __future__ import annotations

import json
from typing import Any


def build_cdk_artifact(blueprint: dict[str, Any], iam_plan: dict[str, Any]) -> dict[str, Any]:
    service_name = blueprint["service_name"]
    stack_name = blueprint["stack_name"]
    slug = service_name.replace("-", "_")
    stack_file = f"lib/{slug}_service_stack.ts"

    files = [
        {
            "path": "package.json",
            "content": _package_json(service_name),
        },
        {
            "path": "tsconfig.json",
            "content": _tsconfig_json(),
        },
        {
            "path": "cdk.json",
            "content": _cdk_json(),
        },
        {
            "path": "bin/app.ts",
            "content": _app_ts(stack_name, slug),
        },
        {
            "path": stack_file,
            "content": _service_stack_ts(blueprint, iam_plan, stack_name),
        },
        {
            "path": "README.generated.md",
            "content": _readme_md(blueprint, iam_plan, stack_file),
        },
        {
            "path": "manifest.json",
            "content": json.dumps(
                {
                    "service_name": service_name,
                    "stack_name": stack_name,
                    "platform": blueprint["platform"],
                    "entrypoint": "bin/app.ts",
                    "stack_file": stack_file,
                },
                indent=2,
            )
            + "\n",
        },
    ]

    return {
        "project_name": f"{service_name}-cdk-artifact",
        "stack_name": stack_name,
        "entrypoint": "bin/app.ts",
        "stack_file": stack_file,
        "files": files,
    }


def _package_json(service_name: str) -> str:
    package_json = {
        "name": f"{service_name}-generated-stack",
        "private": True,
        "version": "0.1.0",
        "scripts": {
            "build": "tsc",
            "synth": "cdk synth",
            "deploy": "cdk deploy --require-approval never",
        },
        "dependencies": {
            "aws-cdk-lib": "^2.140.0",
            "constructs": "^10.3.0",
            "source-map-support": "^0.5.21",
        },
        "devDependencies": {
            "@types/node": "^20",
            "aws-cdk": "^2.140.0",
            "typescript": "~5.4.0",
        },
    }
    return json.dumps(package_json, indent=2) + "\n"


def _tsconfig_json() -> str:
    return json.dumps(
        {
            "compilerOptions": {
                "target": "ES2022",
                "module": "commonjs",
                "lib": ["es2022"],
                "declaration": True,
                "strict": True,
                "noImplicitAny": True,
                "strictNullChecks": True,
                "noImplicitThis": True,
                "alwaysStrict": True,
                "noUnusedLocals": False,
                "noUnusedParameters": False,
                "noImplicitReturns": True,
                "noFallthroughCasesInSwitch": False,
                "inlineSourceMap": True,
                "inlineSources": True,
                "experimentalDecorators": True,
                "strictPropertyInitialization": False,
                "typeRoots": ["./node_modules/@types"],
            },
            "exclude": ["cdk.out"],
        },
        indent=2,
    ) + "\n"


def _cdk_json() -> str:
    return json.dumps({"app": "npx ts-node --prefer-ts-exts bin/app.ts"}, indent=2) + "\n"


def _app_ts(stack_name: str, slug: str) -> str:
    class_name = stack_name
    return (
        "import 'source-map-support/register';\n"
        "import * as cdk from 'aws-cdk-lib';\n"
        f"import {{ {class_name} }} from '../lib/{slug}_service_stack';\n"
        "\n"
        "const app = new cdk.App();\n"
        f"new {class_name}(app, '{stack_name}', {{\n"
        "  env: {\n"
        "    account: process.env.CDK_DEFAULT_ACCOUNT,\n"
        "    region: process.env.CDK_DEFAULT_REGION ?? 'ap-northeast-2',\n"
        "  },\n"
        "});\n"
    )


def _service_stack_ts(blueprint: dict[str, Any], iam_plan: dict[str, Any], stack_name: str) -> str:
    class_name = stack_name
    role_name = iam_plan["role_name"]
    role_statements = _render_policy_statements(iam_plan["inline_statements"])
    dashboard_widgets = _render_dashboard_widgets(blueprint)
    platform_resource = _render_platform_resource(blueprint)
    integration_list = ", ".join(f"'{item}'" for item in blueprint.get("integrations", []))
    environments = ", ".join(f"'{item}'" for item in blueprint.get("environments", []))
    guardrails = ", ".join(f"'{item}'" for item in blueprint.get("guardrails", []))
    service_name = blueprint["service_name"]
    exposure = blueprint["network"]["exposure"]
    health_path = blueprint["network"]["health_check_path"]

    return f"""import * as cdk from 'aws-cdk-lib';
import {{ Construct }} from 'constructs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ssm from 'aws-cdk-lib/aws-ssm';

export class {class_name} extends cdk.Stack {{
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {{
    super(scope, id, props);

    const serviceRole = new iam.Role(this, 'ServiceRole', {{
      roleName: '{role_name}',
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      inlinePolicies: {{
        serviceAccess: new iam.PolicyDocument({{
          statements: [
{role_statements}
          ],
        }}),
      }},
    }});

    const dashboard = new cloudwatch.Dashboard(this, 'ServiceDashboard', {{
      dashboardName: '{service_name}-service-dashboard',
    }});
    dashboard.addWidgets(
{dashboard_widgets}
    );

{platform_resource}

    new ssm.StringParameter(this, 'ServiceBlueprint', {{
      parameterName: '/platform-agent/{service_name}/blueprint',
      stringValue: JSON.stringify({{
        serviceName: '{service_name}',
        platform: '{blueprint["platform"]}',
        exposure: '{exposure}',
        healthCheckPath: '{health_path}',
        integrations: [{integration_list}],
        environments: [{environments}],
        guardrails: [{guardrails}],
      }}),
    }});

    new cdk.CfnOutput(this, 'ServiceRoleArn', {{
      value: serviceRole.roleArn,
    }});
  }}
}}
"""


def _render_policy_statements(statements: list[dict[str, Any]]) -> str:
    rendered: list[str] = []
    for statement in statements:
        actions = ", ".join(f"'{action}'" for action in statement["actions"])
        resources = ", ".join(f"'{resource}'" for resource in statement["resources"])
        rendered.append(
            "            new iam.PolicyStatement({\n"
            f"              sid: '{statement['sid']}',\n"
            f"              actions: [{actions}],\n"
            f"              resources: [{resources}],\n"
            "            }),"
        )
    return "\n".join(rendered)


def _render_dashboard_widgets(blueprint: dict[str, Any]) -> str:
    service_name = blueprint["service_name"]
    widgets = [
        "      new cloudwatch.TextWidget({",
        f"        markdown: '## {service_name}\\nGenerated by platform-agent provisioning emitter.',",
        "        width: 24,",
        "      }),",
    ]

    if blueprint["platform"] == "lambda":
        widgets.extend(
            [
                "      new cloudwatch.GraphWidget({",
                "        title: 'Lambda invocations and errors',",
                "        left: [",
                f"          new cloudwatch.Metric({{ namespace: 'AWS/Lambda', metricName: 'Invocations', dimensionsMap: {{ FunctionName: '{service_name}' }} }}),",
                f"          new cloudwatch.Metric({{ namespace: 'AWS/Lambda', metricName: 'Errors', dimensionsMap: {{ FunctionName: '{service_name}' }} }}),",
                "        ],",
                "        width: 12,",
                "      }),",
            ]
        )
    else:
        widgets.extend(
            [
                "      new cloudwatch.GraphWidget({",
                "        title: 'Service workload health',",
                "        left: [",
                f"          new cloudwatch.Metric({{ namespace: 'PlatformAgent/Workload', metricName: 'RequestCount', dimensionsMap: {{ ServiceName: '{service_name}' }} }}),",
                f"          new cloudwatch.Metric({{ namespace: 'PlatformAgent/Workload', metricName: 'ErrorCount', dimensionsMap: {{ ServiceName: '{service_name}' }} }}),",
                "        ],",
                "        width: 12,",
                "      }),",
            ]
        )

    return "\n".join(widgets)


def _render_platform_resource(blueprint: dict[str, Any]) -> str:
    service_name = blueprint["service_name"]
    platform = blueprint["platform"]
    capacity = blueprint["capacity"]
    if platform == "lambda":
        return f"""    const serviceFunction = new lambda.Function(this, 'ServiceFunction', {{
      functionName: '{service_name}',
      runtime: lambda.Runtime.PYTHON_3_11,
      architecture: lambda.Architecture.ARM_64,
      handler: 'index.handler',
      code: lambda.Code.fromInline(
        'def handler(event, context):\\n'
        '    return {{\"statusCode\": 200, \"body\": \"replace with service code\"}}\\n'
      ),
      memorySize: {capacity["memory"]},
      timeout: cdk.Duration.seconds(30),
      reservedConcurrentExecutions: {blueprint["resources"]["reserved_concurrency"]},
      environment: {{
        SERVICE_NAME: '{service_name}',
      }},
    }});

    new cdk.CfnOutput(this, 'ServiceFunctionName', {{
      value: serviceFunction.functionName,
    }});"""

    return f"""    // This stack intentionally leaves workload rollout to the platform team.
    // It deploys shared guardrails plus a service descriptor that EKS release tooling
    // can consume when rendering manifests or Helm values.
    new ssm.StringParameter(this, 'EksWorkloadDescriptor', {{
      parameterName: '/platform-agent/{service_name}/eks-workload',
      stringValue: JSON.stringify({{
        serviceName: '{service_name}',
        desiredCount: {capacity["desired_count"]},
        cpu: {capacity["cpu"]},
        memory: {capacity["memory"]},
        port: {blueprint["network"]["port"]},
        exposure: '{blueprint["network"]["exposure"]}',
      }}),
    }});"""


def _readme_md(blueprint: dict[str, Any], iam_plan: dict[str, Any], stack_file: str) -> str:
    service_name = blueprint["service_name"]
    return (
        f"# Generated CDK Artifact for {service_name}\n\n"
        "This project was generated by `platform-agent` from a provisioning request.\n\n"
        "## Files\n"
        f"- `{stack_file}` — service stack scaffold\n"
        "- `bin/app.ts` — CDK app entrypoint\n"
        "- `manifest.json` — machine-readable metadata\n\n"
        "## Follow-up\n"
        "1. Replace placeholder ARNs in IAM policies with real resource ARNs.\n"
        "2. For EKS services, attach this descriptor to your workload/Helm pipeline.\n"
        "3. For Lambda services, replace inline placeholder code with your application package.\n\n"
        "## IAM Notes\n"
        + "\n".join(f"- {note}" for note in iam_plan.get("notes", []))
        + "\n"
    )
