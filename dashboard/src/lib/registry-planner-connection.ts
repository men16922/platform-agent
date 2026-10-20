import { attachmentRequest, preparationRequest, PreviewError } from './registry-preview-contract';

export type RegistryOperation = 'preview' | 'prepare' | 'status';
export type PlannerEnvironment = Record<string, string | undefined>;
export interface AwsPlannerConnection {
  mode: 'aws'; functionArn: string; roleArn: string; region: string; storedRequests: boolean;
}
export interface LocalPlannerConnection {
  mode: 'local'; python: string; repo: string; users: string; endpoint: string; table: string;
}
export function plannerConnection(env: PlannerEnvironment): AwsPlannerConnection | LocalPlannerConnection {
  if (env.REGISTRY_PLANNER_MODE === 'local' && !env.VERCEL) {
    const fields = [env.REGISTRY_PLANNER_PYTHON, env.REGISTRY_PLANNER_LOCAL_REPO,
      env.REGISTRY_PLANNER_LOCAL_USERS, env.REGISTRY_PLANNER_LOCAL_PLAN_ENDPOINT,
      env.REGISTRY_PLANNER_LOCAL_PLAN_TABLE];
    if (fields.some(value => !value || value !== value.trim())) throw new PreviewError('planner_not_configured');
    const [python, repo, users, endpoint, table] = fields as string[];
    return {mode:'local', python, repo, users, endpoint, table};
  }
  const arn = env.REGISTRY_PLANNER_FUNCTION_ARN;
  const role = env.REGISTRY_PLANNER_ROLE_ARN;
  const match = /^arn:aws:lambda:([a-z0-9-]+):(\d{12}):function:([A-Za-z0-9_-]+)$/.exec(arn ?? '');
  if (env.REGISTRY_PLANNER_MODE !== 'aws' || !match || arn !== arn?.trim()
      || !role || role !== role.trim()
      || !new RegExp(`^arn:aws:iam::${match[2]}:role/[A-Za-z0-9_+=,.@/-]+$`).test(role)
      || (env.VERCEL && env.VERCEL_ENV !== 'production')) throw new PreviewError('planner_not_configured');
  return {mode:'aws', functionArn:arn!, roleArn:role, region:match[1],
    storedRequests:env.REGISTRY_PLANNER_STORED_REQUESTS === '1'};
}

// Configuration readiness is not a health check or proof of remote deployment.
export function preparationAvailable(env: PlannerEnvironment): boolean {
  try {
    const connection = plannerConnection(env);
    return connection.mode === 'local' || connection.storedRequests;
  } catch { return false; }
}

export function registryInvokeInput(connection: AwsPlannerConnection, operation: RegistryOperation,
  subject: string, request: unknown) {
  if (!['preview','prepare','status'].includes(operation)) throw new PreviewError('invalid_request',422);
  if (operation !== 'preview' && !connection.storedRequests) throw new PreviewError('planner_not_configured');
  if (!subject || subject !== subject.trim() || subject.length > 256 || /[\x00-\x1f\x7f]/.test(subject))
    throw new PreviewError('session_required',401);
  const input = operation === 'preview' ? attachmentRequest(request) : preparationRequest(request);
  return {FunctionName:connection.functionArn, InvocationType:'RequestResponse' as const,
    Payload:new TextEncoder().encode(JSON.stringify({operation, subject, request:input}))};
}
