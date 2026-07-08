"""
Manifest Generator — converts ServiceSpec YAML into Kubernetes manifests.

Usage:
    python -m src.agents.provisioning.manifest_generator examples/orders-api.yaml
    python -m src.agents.provisioning.manifest_generator examples/orders-api.yaml --output /tmp/out.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from src.agents.adapters.deployment.base import ServiceSpec


def load_spec(path: str | Path) -> ServiceSpec:
    """Load a ServiceSpec from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    spec_data = data.get("spec", data)
    metadata = data.get("metadata", {})

    return ServiceSpec(
        name=metadata.get("name", spec_data.get("name", "")),
        image=spec_data.get("image", ""),
        version=spec_data.get("version", "latest"),
        replicas=spec_data.get("replicas", 1),
        ports=spec_data.get("ports", [8080]),
        health_path=spec_data.get("health", spec_data.get("health_path", "/healthz")),
        namespace=spec_data.get("namespace", metadata.get("namespace", "default")),
        provider=spec_data.get("provider", "onprem"),
        resources=spec_data.get("resources", {"cpu": "250m", "memory": "256Mi"}),
        env=spec_data.get("env", {}),
    )


def generate_deployment(spec: ServiceSpec, image_uri: str | None = None) -> dict[str, Any]:
    """Generate a Kubernetes Deployment manifest from a ServiceSpec."""
    if image_uri is None:
        image_uri = f"{spec.image}:{spec.version}"

    container: dict[str, Any] = {
        "name": spec.name,
        "image": image_uri,
        "ports": [{"containerPort": p} for p in spec.ports],
        "resources": {
            "requests": spec.resources,
            "limits": spec.resources,
        },
        "livenessProbe": {
            "httpGet": {"path": spec.health_path, "port": spec.ports[0]},
            "initialDelaySeconds": 5,
            "periodSeconds": 10,
        },
        "readinessProbe": {
            "httpGet": {"path": spec.health_path, "port": spec.ports[0]},
            "initialDelaySeconds": 3,
            "periodSeconds": 5,
        },
    }

    if spec.env:
        container["env"] = [{"name": k, "value": v} for k, v in spec.env.items()]

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": spec.name,
            "namespace": spec.namespace,
            "labels": {"app": spec.name, "version": spec.version},
        },
        "spec": {
            "replicas": spec.replicas,
            "selector": {"matchLabels": {"app": spec.name}},
            "template": {
                "metadata": {
                    "labels": {"app": spec.name, "version": spec.version},
                },
                "spec": {"containers": [container]},
            },
        },
    }


def generate_service(spec: ServiceSpec) -> dict[str, Any]:
    """Generate a Kubernetes Service manifest."""
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": spec.name,
            "namespace": spec.namespace,
            "labels": {"app": spec.name},
        },
        "spec": {
            "selector": {"app": spec.name},
            "ports": [{"port": p, "targetPort": p, "protocol": "TCP"} for p in spec.ports],
            "type": "ClusterIP",
        },
    }


def generate_ingress(spec: ServiceSpec, host: str | None = None) -> dict[str, Any]:
    """Generate a Kubernetes Ingress manifest."""
    if host is None:
        host = f"{spec.name}.local"

    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": f"{spec.name}-ingress",
            "namespace": spec.namespace,
            "annotations": {"nginx.ingress.kubernetes.io/rewrite-target": "/"},
        },
        "spec": {
            "ingressClassName": "nginx",
            "rules": [
                {
                    "host": host,
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": spec.name,
                                        "port": {"number": spec.ports[0]},
                                    }
                                },
                            }
                        ]
                    },
                }
            ],
        },
    }


def generate_manifests(spec: ServiceSpec, image_uri: str | None = None, include_ingress: bool = True) -> list[dict[str, Any]]:
    """Generate all K8s manifests for a ServiceSpec."""
    manifests = [
        generate_deployment(spec, image_uri),
        generate_service(spec),
    ]
    if include_ingress:
        manifests.append(generate_ingress(spec))
    return manifests


def render_yaml(manifests: list[dict[str, Any]]) -> str:
    """Render manifests as multi-document YAML string."""
    docs = []
    for m in manifests:
        docs.append(yaml.dump(m, default_flow_style=False, sort_keys=False))
    return "---\n".join(docs)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = argv or sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("Usage: python -m src.agents.provisioning.manifest_generator <spec.yaml> [--output <path>]")
        sys.exit(0)

    spec_path = args[0]
    output_path = None
    if "--output" in args:
        idx = args.index("--output")
        output_path = args[idx + 1] if idx + 1 < len(args) else None

    spec = load_spec(spec_path)
    manifests = generate_manifests(spec)
    output = render_yaml(manifests)

    if output_path:
        Path(output_path).write_text(output)
        print(f"Written to {output_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
