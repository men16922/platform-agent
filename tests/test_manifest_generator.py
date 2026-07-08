"""
Tests for manifest_generator — ServiceSpec YAML → K8s manifest conversion.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.agents.adapters.deployment.base import ServiceSpec
from src.agents.provisioning.manifest_generator import (
    generate_deployment,
    generate_ingress,
    generate_manifests,
    generate_service,
    load_spec,
    render_yaml,
)


SAMPLE_SPEC_YAML = """\
apiVersion: platform-agent/v1
kind: ServiceDeployment
metadata:
  name: test-api
  namespace: staging
spec:
  image: test-api
  version: v2.0.0
  replicas: 2
  ports: [8080, 9090]
  health: /health
  provider: aws
  resources:
    cpu: 500m
    memory: 512Mi
  env:
    APP_ENV: staging
"""


class TestLoadSpec:
    def test_load_from_yaml(self, tmp_path):
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(SAMPLE_SPEC_YAML)

        spec = load_spec(spec_file)

        assert spec.name == "test-api"
        assert spec.image == "test-api"
        assert spec.version == "v2.0.0"
        assert spec.replicas == 2
        assert spec.ports == [8080, 9090]
        assert spec.health_path == "/health"
        assert spec.namespace == "staging"
        assert spec.provider == "aws"
        assert spec.resources == {"cpu": "500m", "memory": "512Mi"}
        assert spec.env == {"APP_ENV": "staging"}

    def test_load_minimal_spec(self, tmp_path):
        minimal = "metadata:\n  name: minimal\nspec:\n  image: minimal\n"
        spec_file = tmp_path / "minimal.yaml"
        spec_file.write_text(minimal)

        spec = load_spec(spec_file)

        assert spec.name == "minimal"
        assert spec.image == "minimal"
        assert spec.version == "latest"
        assert spec.replicas == 1
        assert spec.namespace == "default"

    def test_load_examples_orders_api(self):
        spec = load_spec("examples/orders-api.yaml")

        assert spec.name == "orders-api"
        assert spec.version == "v1.4.2"
        assert spec.replicas == 3
        assert spec.provider == "onprem"
        assert "DB_HOST" in spec.env


class TestGenerateDeployment:
    def test_basic_deployment(self):
        spec = ServiceSpec(name="app", image="app", version="v1", replicas=2, ports=[8080])
        manifest = generate_deployment(spec)

        assert manifest["apiVersion"] == "apps/v1"
        assert manifest["kind"] == "Deployment"
        assert manifest["metadata"]["name"] == "app"
        assert manifest["metadata"]["namespace"] == "default"
        assert manifest["spec"]["replicas"] == 2

        container = manifest["spec"]["template"]["spec"]["containers"][0]
        assert container["name"] == "app"
        assert container["image"] == "app:v1"
        assert container["ports"] == [{"containerPort": 8080}]
        assert "livenessProbe" in container
        assert "readinessProbe" in container

    def test_custom_image_uri(self):
        spec = ServiceSpec(name="app", image="app", version="v1")
        manifest = generate_deployment(spec, image_uri="123.dkr.ecr.us-east-1.amazonaws.com/app:v1")

        container = manifest["spec"]["template"]["spec"]["containers"][0]
        assert container["image"] == "123.dkr.ecr.us-east-1.amazonaws.com/app:v1"

    def test_env_vars_included(self):
        spec = ServiceSpec(name="app", image="app", version="v1", env={"KEY": "val"})
        manifest = generate_deployment(spec)

        container = manifest["spec"]["template"]["spec"]["containers"][0]
        assert container["env"] == [{"name": "KEY", "value": "val"}]

    def test_no_env_when_empty(self):
        spec = ServiceSpec(name="app", image="app", version="v1")
        manifest = generate_deployment(spec)

        container = manifest["spec"]["template"]["spec"]["containers"][0]
        assert "env" not in container

    def test_labels_include_version(self):
        spec = ServiceSpec(name="app", image="app", version="v2.1")
        manifest = generate_deployment(spec)

        assert manifest["metadata"]["labels"]["version"] == "v2.1"
        assert manifest["spec"]["template"]["metadata"]["labels"]["version"] == "v2.1"


class TestGenerateService:
    def test_basic_service(self):
        spec = ServiceSpec(name="web", image="web", version="v1", ports=[80, 443])
        manifest = generate_service(spec)

        assert manifest["apiVersion"] == "v1"
        assert manifest["kind"] == "Service"
        assert manifest["metadata"]["name"] == "web"
        assert manifest["spec"]["type"] == "ClusterIP"
        assert len(manifest["spec"]["ports"]) == 2
        assert manifest["spec"]["ports"][0] == {"port": 80, "targetPort": 80, "protocol": "TCP"}


class TestGenerateIngress:
    def test_default_host(self):
        spec = ServiceSpec(name="api", image="api", version="v1", ports=[8080])
        manifest = generate_ingress(spec)

        assert manifest["apiVersion"] == "networking.k8s.io/v1"
        assert manifest["kind"] == "Ingress"
        assert manifest["spec"]["rules"][0]["host"] == "api.local"
        backend = manifest["spec"]["rules"][0]["http"]["paths"][0]["backend"]
        assert backend["service"]["name"] == "api"
        assert backend["service"]["port"]["number"] == 8080

    def test_custom_host(self):
        spec = ServiceSpec(name="api", image="api", version="v1", ports=[8080])
        manifest = generate_ingress(spec, host="api.example.com")

        assert manifest["spec"]["rules"][0]["host"] == "api.example.com"


class TestGenerateManifests:
    def test_returns_three_manifests_with_ingress(self):
        spec = ServiceSpec(name="app", image="app", version="v1")
        manifests = generate_manifests(spec)

        assert len(manifests) == 3
        kinds = [m["kind"] for m in manifests]
        assert kinds == ["Deployment", "Service", "Ingress"]

    def test_returns_two_manifests_without_ingress(self):
        spec = ServiceSpec(name="app", image="app", version="v1")
        manifests = generate_manifests(spec, include_ingress=False)

        assert len(manifests) == 2


class TestRenderYaml:
    def test_multi_document_output(self):
        spec = ServiceSpec(name="app", image="app", version="v1")
        manifests = generate_manifests(spec, include_ingress=False)
        output = render_yaml(manifests)

        assert "---" in output
        assert "kind: Deployment" in output
        assert "kind: Service" in output

    def test_output_is_valid_yaml(self):
        import yaml

        spec = ServiceSpec(name="app", image="app", version="v1")
        manifests = generate_manifests(spec)
        output = render_yaml(manifests)

        docs = list(yaml.safe_load_all(output))
        assert len(docs) == 3
        assert docs[0]["kind"] == "Deployment"
