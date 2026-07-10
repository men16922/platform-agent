# Dashboard Live Data — AWS incident slice

## Scope

The first live-data slice is deliberately read-only:

- **Live:** AWS `incident-history` records on Overview and Incidents.
- **Demo:** deployments, provider health, and agent activity.
- **Not included:** approval/execution buttons, browser-side cloud credentials, GCP Firestore, Azure Cosmos DB, or user authentication.

The UI labels each dataset as `LIVE · AWS`, `DEMO DATA`, or `DEMO FALLBACK`. A failed AWS read falls back to demo data without presenting it as live.

## Security model

Vercel obtains short-lived AWS credentials through OIDC. The IAM role can only read the `incident-history` DynamoDB table. No long-lived `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` is stored in Vercel.

Trust is scoped to one Vercel team, one Vercel project, and the `production` / `preview` environments.

## AWS deployment

Find the team slug in the Vercel team URL and the project name in Project Settings. Then synthesize and deploy the stack:

```bash
cd src/stacks
npx cdk synth \
  -c vercelTeamSlug=<team-slug> \
  -c vercelProjectName=<project-name>
npx cdk deploy \
  -c vercelTeamSlug=<team-slug> \
  -c vercelProjectName=<project-name>
```

If the AWS account already has the Vercel OIDC provider, also pass:

```bash
-c vercelOidcProviderArn=arn:aws:iam::<account-id>:oidc-provider/oidc.vercel.com/<team-slug>
```

Copy the `VercelDashboardRoleArn` CloudFormation output.

## Vercel configuration

1. Project Settings → Security → enable Secure Backend Access with OIDC, Team issuer mode.
2. Add these Environment Variables for Production and Preview:
   - `DASHBOARD_DATA_SOURCE=aws`
   - `PLATFORM_AWS_REGION=us-east-1`
   - `DASHBOARD_INCIDENT_TABLE=incident-history`
   - `AWS_ROLE_ARN=<VercelDashboardRoleArn>`
3. Redeploy and verify `/api/dashboard/incidents` returns `source: "aws-live"`.

## Current limitation

The read uses a bounded DynamoDB Scan of up to 100 records and sorts them by timestamp in the Vercel function. Before high-volume production use, add a time-ordered read model or GSI instead of expanding the Scan.

## Current deployment

- AWS OIDC provider and read-only role: deployed 2026-07-11.
- Production: `https://platform-agent-red.vercel.app`.
- Production API verification: `source=aws-live`; current incident count is 0.
