import { NextResponse } from "next/server";
import { getDeploymentFeed } from "@/lib/activity-data";

export const dynamic = "force-dynamic";

export async function GET() {
  const feed = await getDeploymentFeed();
  return NextResponse.json(feed);
}
