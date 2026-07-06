"""Generate platform-agent architecture diagram using the diagrams library."""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda, EKS, ECR
from diagrams.aws.integration import Eventbridge, StepFunctions, SQS, SNS
from diagrams.aws.database import Dynamodb
from diagrams.aws.ml import Sagemaker
from diagrams.gcp.compute import GKE
from diagrams.gcp.devtools import ContainerRegistry as GcpAR
from diagrams.azure.compute import KubernetesServices as AzureAKS
from diagrams.azure.containers import ContainerRegistries as AzureACR
from diagrams.onprem.container import Docker
from diagrams.onprem.client import User
from diagrams.generic.blank import Blank

graph_attr = {
    "fontsize": "24",
    "bgcolor": "white",
    "pad": "0.8",
    "nodesep": "0.6",
    "ranksep": "1.0",
}

with Diagram(
    "Platform Agent — Multi-Cloud AI Deployment",
    filename="/Users/men1692/Desktop/AWS/platform-agent/docs/architecture-diagram",
    show=False,
    direction="TB",
    graph_attr=graph_attr,
    outformat="png",
):
    user = User("User\n(Natural Language)")

    with Cluster("AI Agent Layer (Autonomous Deployment)"):
        strands = Lambda("Strands Agent\n(AWS — Bedrock)")
        adk = GKE("ADK Agent\n(GCP — Gemini)")
        msft = AzureAKS("MS Agent Framework\n(Azure — GPT-4o)")

    with Cluster("Policy Gate"):
        guardian = Lambda("Guardian Agent\nAPPROVE / AUTO / REJECT")

    with Cluster("E2E Pipeline DAG (plan → guard → build → push → deploy → validate → report)"):
        pipeline = StepFunctions("Pipeline\nOrchestrator")

    with Cluster("Multi-Cloud Targets"):
        with Cluster("AWS"):
            ecr = ECR("ECR")
            eks = EKS("EKS")
        with Cluster("GCP"):
            ar = GcpAR("Artifact\nRegistry")
            gke = GKE("GKE\nAutopilot")
        with Cluster("Azure"):
            acr = AzureACR("ACR")
            aks = AzureAKS("AKS")
        with Cluster("On-Prem"):
            kind_local = Docker("kind\nCluster")

    with Cluster("Gateway"):
        mcp = Lambda("MCP Server\n(kubectl/docker)")
        a2a = Lambda("A2A Server\n(Protocol v1.0)")

    with Cluster("AWS Operations (CDK — EventBridge + Step Functions)"):
        eb = Eventbridge("EventBridge\n(Alarm/Schedule)")
        sfn = StepFunctions("Incident\nPipeline")
        ops_lambdas = Lambda("Detect → Analyze\n→ Decide → Execute")
        ddb = Dynamodb("DynamoDB\n(History/Runbooks)")
        slack = SNS("Slack\nNotification")

    # User → Agents
    user >> Edge(color="darkblue", style="bold") >> strands
    user >> Edge(color="darkgreen", style="bold") >> adk
    user >> Edge(color="purple", style="bold") >> msft

    # Agents → Guardian → Pipeline
    strands >> Edge(color="red", label="policy check") >> guardian
    adk >> guardian
    msft >> guardian
    guardian >> Edge(color="green", label="AUTO") >> pipeline

    # Pipeline → Targets
    pipeline >> Edge(color="orange") >> ecr >> eks
    pipeline >> Edge(color="orange") >> ar >> gke
    pipeline >> Edge(color="orange") >> acr >> aks
    pipeline >> Edge(color="orange") >> kind_local

    # Gateway
    strands >> Edge(style="dashed") >> mcp
    a2a >> Edge(style="dashed") >> adk

    # Operations
    eb >> sfn >> ops_lambdas >> ddb
    ops_lambdas >> slack
