import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";
import { SFNClient } from "@aws-sdk/client-sfn";
import { awsCredentialsProvider } from "@vercel/oidc-aws-credentials-provider";

const DEFAULT_REGION = "us-east-1";

let documentClient: DynamoDBDocumentClient | null = null;
let sfnClient: SFNClient | null = null;

export function getDocumentClient(): DynamoDBDocumentClient {
  if (documentClient) {
    return documentClient;
  }

  const region = process.env.PLATFORM_AWS_REGION ?? DEFAULT_REGION;
  const roleArn = process.env.AWS_ROLE_ARN;

  if (process.env.VERCEL && !roleArn) {
    throw new Error("AWS_ROLE_ARN is required for live data on Vercel");
  }

  const client = new DynamoDBClient({
    region,
    credentials: roleArn
      ? awsCredentialsProvider({ roleArn, clientConfig: { region } })
      : undefined,
  });

  documentClient = DynamoDBDocumentClient.from(client, {
    marshallOptions: { removeUndefinedValues: true },
  });

  return documentClient;
}

export function getSFNClient(): SFNClient {
  if (sfnClient) {
    return sfnClient;
  }

  const region = process.env.PLATFORM_AWS_REGION ?? DEFAULT_REGION;
  const roleArn = process.env.AWS_ROLE_ARN;

  if (process.env.VERCEL && !roleArn) {
    throw new Error("AWS_ROLE_ARN is required for live data on Vercel");
  }

  sfnClient = new SFNClient({
    region,
    credentials: roleArn
      ? awsCredentialsProvider({ roleArn, clientConfig: { region } })
      : undefined,
  });

  return sfnClient;
}

export async function getDeploymentStateMachineArn(): Promise<string | null> {
  const { ListStateMachinesCommand } = await import("@aws-sdk/client-sfn");
  try {
    const client = getSFNClient();
    const res = await client.send(new ListStateMachinesCommand({ maxResults: 100 }));
    const sm = res.stateMachines?.find(
      (s) => s.name?.includes("DeploymentPipeline") || s.name?.includes("platform-agent-deployment")
    );
    return sm?.stateMachineArn || null;
  } catch (error) {
    console.error("aws-client.getDeploymentStateMachineArn.failed", error);
    return null;
  }
}
