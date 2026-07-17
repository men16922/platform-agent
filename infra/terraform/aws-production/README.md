# aws-production — Terraform module (reference #7-b)

Cloud substrate for running the On-Prem control plane (the Helm chart in
`infra/helm/platform-agent`) as a production service on AWS:

| Piece | What | Why our code needs it |
|---|---|---|
| VPC | 2 AZ, public+private, 1 NAT | EKS/Aurora placement |
| EKS | v1.31 + 1 managed node group | substrate for the Helm chart |
| Aurora PostgreSQL Serverless v2 | min 0.5 ACU, AWS-managed password | the `PLATFORM_STATE_DSN` State Store (roadmap ④) — unlocks `replicas > 1` |
| IRSA | OIDC provider + role for the chart SA | DynamoDB activity-table writes (`PLATFORM_ACTIVITY_TABLE`), scoped to the exact table ARN |

**Deliberately omitted** (reference lists them; our shipped code consumes
neither): Redis — the state seam is PostgreSQL-only today; Cognito — the
dashboard authenticates with GitHub OAuth via Auth.js. Add them when a
consumer exists, not before.

IAM posture matches the repo guardrail: policies we author enumerate actions
against exact ARNs — no `Resource: "*"` (AWS-managed EKS policies are attached
by ARN as required by EKS itself).

## Usage

```sh
cd infra/terraform/aws-production
terraform init
terraform plan            # needs AWS credentials
terraform apply           # ⚠ billable: EKS ~$0.10/h control plane + nodes + NAT + Aurora
```

Then wire the chart onto it:

```sh
aws eks update-kubeconfig --name platform-agent-eks
kubectl create secret generic pa-state-dsn \
  --from-literal=dsn="postgresql://platform_agent:<password-from-managed-secret>@<aurora_endpoint>:5432/platform_state"
helm install pa ../../helm/platform-agent \
  --set persistence.enabled=false \
  --set webhook.replicas=2 \
  --set stateStore.existingSecret=pa-state-dsn
kubectl annotate sa pa-platform-agent eks.amazonaws.com/role-arn=<chart_irsa_role_arn>
```

`terraform destroy` tears the whole substrate down (Aurora skips the final
snapshot by design — this is a reference stack, not a data custodian).

## Verified

`terraform init` + `terraform fmt -check` + `terraform validate` run offline
(no credentials, no spend). `plan`/`apply` are user-gated — this module has
NOT been applied by the harness.
