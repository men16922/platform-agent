import { auth } from '@/auth';
import { attachmentStatus } from '@/lib/registry-preview';
import { checkPreviewOrigin, readPreparationRequest, PreviewError } from '@/lib/registry-preview-contract';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export async function POST(request: Request) {
  const headers = {'Cache-Control':'no-store'};
  try {
    const session = await auth();
    if (!session?.user?.username) throw new PreviewError('session_required', 401);
    const origin = process.env.REGISTRY_PREVIEW_ORIGIN || process.env.AUTH_URL
      || (!process.env.VERCEL ? new URL(request.url).origin : undefined);
    checkPreviewOrigin(request, origin);
    const input = await readPreparationRequest(request);
    const observation = await attachmentStatus(session.user.username, input);
    return Response.json({ok:true, observation}, {headers});
  } catch (error) {
    const failure = error instanceof PreviewError ? error : new PreviewError('planner_unavailable');
    return Response.json({ok:false, error:failure.code}, {status:failure.status, headers});
  }
}
