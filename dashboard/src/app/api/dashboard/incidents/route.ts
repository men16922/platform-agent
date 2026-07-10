import { getIncidentFeed } from "@/lib/incident-data";

export const dynamic = "force-dynamic";

export async function GET() {
  const feed = await getIncidentFeed();
  return Response.json(feed, {
    headers: {
      "Cache-Control": "public, max-age=0, s-maxage=30, stale-while-revalidate=60",
    },
  });
}
