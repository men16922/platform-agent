import { NextResponse } from "next/server";
import { getProviderHealthFeed } from "@/lib/activity-data";

export const dynamic = "force-dynamic";

export async function GET() {
  const feed = await getProviderHealthFeed();
  return NextResponse.json(feed);
}
