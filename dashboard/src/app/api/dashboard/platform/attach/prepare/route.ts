import { auth } from '@/auth';
import { prepareAttachment } from '@/lib/registry-preview';
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
    // Current role/write grants are checked by Python. Cached session role is
    // deliberately not forwarded, and the request cannot choose a subject.
    const preparation = await prepareAttachment(session.user.username, input);
    return Response.json({ok:true, preparation}, {headers});
  } catch (error) {
    const failure = error instanceof PreviewError ? error : new PreviewError('planner_unavailable');
    return Response.json({ok:false, error:failure.code}, {status:failure.status, headers});
  }
}
