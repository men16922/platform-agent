import { NextResponse } from "next/server";
import { getAgentActivityFeed } from "@/lib/activity-data";

export const dynamic = "force-dynamic";

export async function GET() {
  const feed = await getAgentActivityFeed();
  return NextResponse.json(feed);
}
