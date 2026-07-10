# Platform Agent Dashboard

Next.js operations console for the platform-agent portfolio deployment.

The default data source is an explicit demo dataset. AWS incident history can be read live through a Vercel OIDC role; deployments and agent activity remain demo data until their durable read models are implemented.

## Getting Started

Install dependencies and run the development server:

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

Use `DASHBOARD_DATA_SOURCE=demo` for the public demo dataset. For the read-only AWS incident feed, follow `../docs/DASHBOARD_LIVE_DATA.md` and set `DASHBOARD_DATA_SOURCE=aws`.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Data contract

- `GET /api/dashboard/incidents` returns `{ incidents, source, syncedAt, notice? }`.
- `source=aws-live` means DynamoDB was read using short-lived OIDC credentials.
- `source=demo` is the intentional local/public demo mode.
- `source=demo-fallback` means live mode was requested but AWS was unavailable.

Never add long-lived AWS access keys to Vercel. The live path is designed for `AWS_ROLE_ARN` plus Vercel OIDC federation.
