import { LambdaClient, InvokeCommand } from '@aws-sdk/client-lambda';
import { awsCredentialsProvider } from '@vercel/oidc-aws-credentials-provider';
import { execFile } from 'node:child_process';
import { decodePreview, decodePreparation, decodeAttachmentStatus, readStoredInvocation, PreviewError, type AttachmentRequest } from './registry-preview-contract';

import { plannerConnection, registryInvokeInput, type RegistryOperation, type LocalPlannerConnection, type AwsPlannerConnection } from './registry-planner-connection';

async function invokeLocal(connection: LocalPlannerConnection, event: {subject: string; request: unknown}, operation: RegistryOperation) {
  return await new Promise<string>((resolve, reject) => {
    const child = execFile(connection.python,
      ['-m', 'src.agents.platform.registry_local', ...(operation === 'preview' ? [] : [`--${operation}`])], {
        cwd: connection.repo,
        timeout: 15000, maxBuffer: 1024 * 1024,
      }, (error, stdout) => error ? reject(new PreviewError('planner_unavailable')) : resolve(stdout));
    child.stdin?.on('error', () => reject(new PreviewError('planner_unavailable')));
    child.stdin?.end(JSON.stringify(event));
  });
}

export function createPlannerClient(connection: AwsPlannerConnection) {
  return new LambdaClient({region:connection.region, maxAttempts:1,
    credentials:awsCredentialsProvider({roleArn:connection.roleArn,
      clientConfig:{region:connection.region}})});
}

// No writer or publication credentials: this call only persists/claims/observes.
async function invokeAws(operation: RegistryOperation, subject: string, request: unknown) {
  const connection = plannerConnection(process.env);
  if (connection.mode !== 'aws') throw new PreviewError('planner_not_configured');
  // Validate operation, capability opt-in and exact body before obtaining credentials.
  const input = registryInvokeInput(connection, operation, subject, request);
  let client: LambdaClient | undefined;
  try {
    client = createPlannerClient(connection);
    return await client.send(new InvokeCommand(input), {abortSignal:AbortSignal.timeout(65000)});
  } catch {
    throw new PreviewError('planner_invoke_failed');
  } finally { client?.destroy(); }
}

async function invokeStored(operation: 'prepare'|'status', subject: string, request: {request_id:string}) {
  const connection = plannerConnection(process.env);
  if (connection.mode === 'local') return invokeLocal(connection, {subject,request}, operation);
  const response = await invokeAws(operation, subject, request);
  return readStoredInvocation(response.Payload, response.FunctionError, response.StatusCode);
}

export async function prepareAttachment(subject: string, request: {request_id: string}) {
  return decodePreparation(await invokeStored('prepare',subject,request), request.request_id);
}

export async function attachmentStatus(subject: string, request: {request_id: string}) {
  return decodeAttachmentStatus(await invokeStored('status',subject,request), request.request_id);
}

export async function previewAttachment(subject: string, request: AttachmentRequest) {
  const connection = plannerConnection(process.env);
  if (connection.mode === 'local') {
    const output = await invokeLocal(connection, {subject,request}, 'preview');
    return decodePreview(new TextEncoder().encode(output), undefined, 200, request);
  }
  const response = await invokeAws('preview',subject,request);
  return decodePreview(response.Payload, response.FunctionError, response.StatusCode, request);
}
