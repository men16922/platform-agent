import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export interface RegistryPlannerProps extends cdk.StackProps {
  assetPath: string;
  usersTableArn: string;
  repository: string;
  branch: string;
  vercelTeam: string;
  vercelProject: string;
  oidcProviderArn: string;
}

/** Standalone stored planner: never mutates the existing incident stack. */
export class RegistryPlannerStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: RegistryPlannerProps) {
    super(scope, id, props);
    const slug = /^[A-Za-z0-9_-]+$/;
    if (!slug.test(props.vercelTeam) || !slug.test(props.vercelProject)
        || !/^[A-Za-z0-9_-]+\/[A-Za-z0-9_.-]+$/.test(props.repository)
        || !/^[A-Za-z0-9][A-Za-z0-9_./-]{0,199}$/.test(props.branch)
        || props.branch.includes('..')) throw new Error('Invalid planner configuration');
    const table = /^arn:aws:dynamodb:([a-z0-9-]+):(\d{12}):table\/([A-Za-z0-9_.-]+)$/.exec(props.usersTableArn);
    if (!table || table[1] !== this.region || table[2] !== this.account)
      throw new Error('Users table must be an exact ARN in this stack account/region');
    const host = `oidc.vercel.com/${props.vercelTeam}`;
    if (props.oidcProviderArn !== `arn:aws:iam::${this.account}:oidc-provider/${host}`)
      throw new Error('Import the exact existing team OIDC provider ARN');

    const plans = new dynamodb.Table(this, 'Plans', {
      partitionKey: { name: 'request_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl', deletionProtection: true,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });
    const logGroup = new logs.LogGroup(this, 'Logs', {
      retention: logs.RetentionDays.ONE_MONTH, removalPolicy: cdk.RemovalPolicy.RETAIN,
    });
    const execution = new iam.Role(this, 'ExecutionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
    });
    execution.addToPolicy(new iam.PolicyStatement({
      actions: ['dynamodb:GetItem'], resources: [props.usersTableArn],
    }));
    // Plan CAS needs only these item operations; user records stay read-only.
    execution.addToPolicy(new iam.PolicyStatement({
      actions: ['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:UpdateItem'],
      resources: [plans.tableArn],
    }));
    // Only streams in this precreated log group, not account-wide log creation.
    execution.addToPolicy(new iam.PolicyStatement({
      actions: ['logs:CreateLogStream', 'logs:PutLogEvents'], resources: [logGroup.logGroupArn],
    }));
    const fn = new lambda.Function(this, 'Planner', {
      runtime: lambda.Runtime.PYTHON_3_13, architecture: lambda.Architecture.ARM_64,
      handler: 'src.agents.platform.registry_lambda.handler',
      code: lambda.Code.fromAsset(props.assetPath), role: execution, logGroup,
      timeout: cdk.Duration.seconds(60), memorySize: 256,
      environment: {
        REGISTRY_USERS_TABLE: table[3], REGISTRY_PLANS_TABLE: plans.tableName,
        REGISTRY_REPOSITORY: props.repository,
        REGISTRY_BRANCH: props.branch,
      },
    });
    const invokeRole = new iam.Role(this, 'ProductionInvokeRole', {
      assumedBy: new iam.WebIdentityPrincipal(props.oidcProviderArn, {
        StringEquals: {
          [`${host}:aud`]: `https://vercel.com/${props.vercelTeam}`,
          [`${host}:sub`]: `owner:${props.vercelTeam}:project:${props.vercelProject}:environment:production`,
        },
      }),
    });
    invokeRole.addToPolicy(new iam.PolicyStatement({
      actions: ['lambda:InvokeFunction'], resources: [fn.functionArn],
    }));
    new cdk.CfnOutput(this, 'PlansTableName', { value: plans.tableName });
    new cdk.CfnOutput(this, 'PlannerArn', { value: fn.functionArn });
    new cdk.CfnOutput(this, 'ProductionInvokeRoleArn', { value: invokeRole.roleArn });
  }
}
