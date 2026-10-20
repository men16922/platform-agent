export interface AttachmentRequest { tenant: string; env: string; capability: string; version: string }
export interface AttachmentPreview {
  contract_version: string; request_id: string; base_commit: string;
  catalog_blob: string; tenant_blob: string; values_path: string; values_blob: string;
  path: string; diff: string; output_sha256: string; digest: string; expires_at: string;
}
export interface AttachmentStatus {
  request_id: string; state: 'PREVIEW' | 'CLAIMED'; published: false;
  expires_at: string; expired: boolean;
}
export class PreviewError extends Error {
  constructor(public code: string, public status = 503) { super(code); }
}
export function attachmentRequest(value: unknown): AttachmentRequest {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new PreviewError('invalid_request', 422);
  const data = value as Record<string, unknown>;
  if (Object.keys(data).sort().join(',') !== 'capability,env,tenant,version') throw new PreviewError('invalid_request', 422);
  for (const [key, value] of Object.entries(data)) {
    const pattern = key === 'version' ? /^[A-Za-z0-9][A-Za-z0-9.+_-]{0,127}$/ : /^[a-z0-9][a-z0-9-]{0,62}$/;
    if (typeof value !== 'string' || value !== value.trim() || !pattern.test(value)) throw new PreviewError('invalid_request', 422);
  }
  return { tenant: data.tenant as string, env: data.env as string,
    capability: data.capability as string, version: data.version as string };
}
export function checkPreviewOrigin(request: Request, configuredOrigin: string | undefined) {
  if (!configuredOrigin) throw new PreviewError('planner_not_configured');
  if (request.headers.get('origin') !== new URL(configuredOrigin).origin
      || request.headers.get('x-registry-preview') !== '1'
      || !['same-origin', null].includes(request.headers.get('sec-fetch-site'))) {
    throw new PreviewError('cross_origin_request', 403);
  }
  if (request.headers.get('content-type')?.split(';')[0].trim() !== 'application/json')
    throw new PreviewError('invalid_content_type', 415);
}
export async function readPreviewRequest(request: Request): Promise<AttachmentRequest> {
  return attachmentRequest(await readBoundedRequest(request));
}
export async function readPreparationRequest(request: Request): Promise<{request_id: string}> {
  return preparationRequest(await readBoundedRequest(request));
}
export function preparationRequest(value: unknown): {request_id: string} {
  if (!value || typeof value !== 'object' || Array.isArray(value)
      || Object.keys(value).join(',') !== 'request_id'
      || !('request_id' in value) || typeof value.request_id !== 'string'
      || value.request_id !== value.request_id.trim()
      || !/^[A-Za-z0-9_-]{1,128}$/.test(value.request_id))
    throw new PreviewError('invalid_request', 422);
  return {request_id: value.request_id};
}
async function readBoundedRequest(request: Request) {
  const reader = request.body?.getReader();
  if (!reader) throw new PreviewError('invalid_request', 422);
  try {
    const chunks: Uint8Array[] = []; let size = 0;
    while (true) {
      const {done, value} = await reader.read(); if (done) break;
      size += value.byteLength;
      if (size > 4096) {
        // Cleanup must not delay or replace the already-decided 413 response.
        void reader.cancel().catch(() => {});
        throw new PreviewError('request_too_large', 413);
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size); let at = 0;
    for (const chunk of chunks) { bytes.set(chunk, at); at += chunk.length; }
    return JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(bytes));
  } catch (error) {
    if (error instanceof PreviewError) throw error;
    throw new PreviewError('invalid_request', 422);
  } finally {
    reader.releaseLock();
  }
}

export function decodePreview(payload: Uint8Array | undefined, functionError: string | undefined,
  statusCode: number | undefined, request: AttachmentRequest): AttachmentPreview {
  if (functionError || statusCode !== 200) throw new PreviewError('planner_invoke_failed');
  if (!payload || payload.length > 1024 * 1024) throw new PreviewError('invalid_planner_response');
  let body;
  try { body = JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(payload)); }
  catch { throw new PreviewError('invalid_planner_response'); }
  if (body?.ok === false && [401,403,409,422,503].includes(body.status)
      && typeof body.error === 'string' && /^[a-z_]{1,80}$/.test(body.error) && body.error === body.error.trim())
    throw new PreviewError(body.error, body.status);
  const plan = body?.plan;
  if (body?.ok !== true || body.status !== 200 || !plan || plan.contract_version !== 'registry-attachment/v1')
    throw new PreviewError('invalid_planner_response');
  const fields = ['contract_version','request_id','base_commit','catalog_blob','tenant_blob','values_path',
    'values_blob','path','diff','output_sha256','digest','expires_at'];
  if (Object.keys(plan).sort().join(',') !== [...fields].sort().join(',')
      || fields.some(key => typeof plan[key] !== 'string')
      || fields.filter(key => key !== 'diff').some(key => plan[key] !== plan[key].trim())
      || !['base_commit','catalog_blob','tenant_blob','values_blob'].every(key => /^[a-f0-9]{40}$/.test(plan[key]))
      || !['digest','output_sha256'].every(key => /^[a-f0-9]{64}$/.test(plan[key]))
      || plan.path !== `platform/tenants/${request.tenant}.yaml`
      || !plan.diff.startsWith(`--- a/${plan.path}\n+++ b/${plan.path}\n`)
      || !/^infra\/onprem\/addons\/values\/[A-Za-z0-9][A-Za-z0-9_-]*\.yaml$/.test(plan.values_path)
      || !/^[A-Za-z0-9_-]{1,128}$/.test(plan.request_id)
      || !Number.isFinite(Date.parse(plan.expires_at))) throw new PreviewError('invalid_planner_response');
  if (Date.parse(plan.expires_at) <= Date.now()) throw new PreviewError('plan_expired', 409);
  return plan as AttachmentPreview;
}

export function decodePreparation(output: string, requestId: string) {
  if (new TextEncoder().encode(output).length > 4096) throw new PreviewError('invalid_planner_response');
  let body;
  try { body = JSON.parse(output); } catch { throw new PreviewError('invalid_planner_response'); }
  if (body?.ok === false && [401,403,404,409,422,503].includes(body.status)
      && typeof body.error === 'string' && /^[a-z_]{1,80}$/.test(body.error) && body.error === body.error.trim())
    throw new PreviewError(body.error, body.status);
  const receipt = body?.preparation;
  if (body?.ok !== true || body.status !== 200 || !receipt
      || Object.keys(receipt).sort().join(',') !== 'published,request_id,state'
      || receipt.request_id !== requestId || receipt.state !== 'CLAIMED' || receipt.published !== false)
    throw new PreviewError('invalid_planner_response');
  return {request_id: requestId, state: 'CLAIMED' as const, published: false as const};
}

export function decodeAttachmentStatus(output: string, requestId: string): AttachmentStatus {
  if (new TextEncoder().encode(output).length > 4096) throw new PreviewError('invalid_planner_response');
  let body;
  try { body = JSON.parse(output); } catch { throw new PreviewError('invalid_planner_response'); }
  if (body?.ok === false && [401,403,404,409,422,503].includes(body.status)
      && typeof body.error === 'string' && /^[a-z_]{1,80}$/.test(body.error) && body.error === body.error.trim())
    throw new PreviewError(body.error, body.status);
  const observation = body?.observation;
  if (body?.ok !== true || body.status !== 200 || !observation
      || Object.keys(observation).sort().join(',') !== 'expired,expires_at,published,request_id,state'
      || observation.request_id !== requestId || !['PREVIEW','CLAIMED'].includes(observation.state)
      || observation.published !== false || typeof observation.expired !== 'boolean'
      || typeof observation.expires_at !== 'string'
      || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(observation.expires_at)
      || !Number.isFinite(Date.parse(observation.expires_at)))
    throw new PreviewError('invalid_planner_response');
  return observation as AttachmentStatus;
}


export function readStoredInvocation(payload: Uint8Array | undefined, functionError: string | undefined,
  statusCode: number | undefined): string {
  if (functionError || statusCode !== 200) throw new PreviewError('planner_invoke_failed');
  if (!payload || payload.byteLength > 4096) throw new PreviewError('invalid_planner_response');
  try { return new TextDecoder('utf-8', {fatal:true}).decode(payload); }
  catch { throw new PreviewError('invalid_planner_response'); }
}
