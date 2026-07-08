"""
Orchestrator — CLI entry point for the E2E deployment pipeline.

Usage:
    python -m src.agents.ai.orchestrator --service orders-api --version v1.4.2 --env staging --provider onprem
"""

from __future__ import annotations

import argparse
import sys

from src.agents.ai.pipeline import DeployPipeline, PipelineSpec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Platform Agent — E2E Deployment Pipeline")
    parser.add_argument("--service", required=True, help="Service name")
    parser.add_argument("--version", required=True, help="Version to deploy")
    parser.add_argument("--env", default="dev", help="Target environment (dev/staging/prod)")
    parser.add_argument("--provider", default="onprem", help="Cloud provider (onprem/aws/gcp/azure)")
    parser.add_argument("--replicas", type=int, default=1, help="Number of replicas")
    parser.add_argument("--namespace", default="default", help="Kubernetes namespace")
    parser.add_argument("--context-path", default=".", help="Docker build context path")

    args = parser.parse_args(argv)

    spec = PipelineSpec(
        service_name=args.service,
        version=args.version,
        environment=args.env,
        provider=args.provider,
        replicas=args.replicas,
        namespace=args.namespace,
        context_path=args.context_path,
    )

    print(f"🚀 Starting pipeline: {spec.service_name}@{spec.version} → {spec.environment} ({spec.provider})")
    print()

    pipeline = DeployPipeline()
    result = pipeline.run(spec)

    print(result.summary())
    print()

    if result.success:
        print("✅ Pipeline completed successfully!")
        return 0
    elif result.final_status.value == "blocked":
        print("⏸  Pipeline paused — waiting for approval.")
        return 2
    else:
        print(f"❌ Pipeline failed at: {result.failed_step.step_name if result.failed_step else 'unknown'}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
