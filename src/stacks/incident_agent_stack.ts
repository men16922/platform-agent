import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as path from 'path';

export class IncidentAgentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ─────────────────────────────────────────────────────────
    // DynamoDB 테이블
    // ─────────────────────────────────────────────────────────

    // 인시던트 이력 (Analyzer: 유사 인시던트 조회 / Executor: 기록)
    const incidentTable = new dynamodb.Table(this, 'IncidentHistory', {
      tableName:   'incident-history',
      partitionKey: { name: 'alarm_name',  type: dynamodb.AttributeType.STRING },
      sortKey:      { name: 'incident_id', type: dynamodb.AttributeType.STRING },
      billingMode:  dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // 런북 레지스트리 (Decision: 알람별 맞춤 런북)
    const runbookTable = new dynamodb.Table(this, 'IncidentRunbooks', {
      tableName:   'incident-runbooks',
      partitionKey: { name: 'alarm_name', type: dynamodb.AttributeType.STRING },
      billingMode:  dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const approvalRequestTable = new dynamodb.Table(this, 'ApprovalRequests', {
      tableName: 'incident-approval-requests',
      partitionKey: { name: 'approval_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // 대시보드 활동 읽기 모델 — 배포/에이전트 활동/프로바이더 헬스
    const activityTable = new dynamodb.Table(this, 'PlatformAgentActivity', {
      tableName:   'platform-agent-activity',
      partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
      sortKey:      { name: 'SK', type: dynamodb.AttributeType.STRING },
      billingMode:  dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    activityTable.addGlobalSecondaryIndex({
      indexName: 'GSI1',
      partitionKey: { name: 'GSI1PK', type: dynamodb.AttributeType.STRING },
      sortKey:      { name: 'GSI1SK', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Vercel Dashboard read path — short-lived OIDC credentials, DynamoDB read-only.
    // Enable with CDK context:
    //   -c vercelTeamSlug=<team> -c vercelProjectName=<project>
    // Optionally reuse an account-level provider with:
    //   -c vercelOidcProviderArn=<provider-arn>
    const vercelTeamSlug = this.node.tryGetContext('vercelTeamSlug') as string | undefined;
    const vercelProjectName = this.node.tryGetContext('vercelProjectName') as string | undefined;
    const vercelOidcProviderArn = this.node.tryGetContext('vercelOidcProviderArn') as string | undefined;
    let vercelDashboardRole: iam.Role | undefined;

    if (vercelTeamSlug && vercelProjectName) {
      const providerHost = `oidc.vercel.com/${vercelTeamSlug}`;
      const providerUrl = `https://${providerHost}`;
      const audience = `https://vercel.com/${vercelTeamSlug}`;
      const oidcProvider: iam.IOpenIdConnectProvider = vercelOidcProviderArn
        ? iam.OpenIdConnectProvider.fromOpenIdConnectProviderArn(
            this,
            'ImportedVercelOidcProvider',
            vercelOidcProviderArn,
          )
        : new iam.OpenIdConnectProvider(this, 'VercelOidcProvider', {
            url: providerUrl,
            clientIds: [audience],
          });

      vercelDashboardRole = new iam.Role(this, 'VercelDashboardReadRole', {
        roleName: 'platform-agent-vercel-dashboard-read',
        description: 'Read-only incident feed for the Vercel platform-agent dashboard',
        assumedBy: new iam.WebIdentityPrincipal(oidcProvider.openIdConnectProviderArn, {
          StringEquals: {
            [`${providerHost}:aud`]: audience,
          },
          StringLike: {
            [`${providerHost}:sub`]: [
              `owner:${vercelTeamSlug}:project:${vercelProjectName}:environment:production`,
              `owner:${vercelTeamSlug}:project:${vercelProjectName}:environment:preview`,
            ],
          },
        }),
      });
      incidentTable.grantReadData(vercelDashboardRole);
      activityTable.grantReadData(vercelDashboardRole);
    }

    // ─────────────────────────────────────────────────────────
    // SNS (알림 & 승인)
    // ─────────────────────────────────────────────────────────

    const alertTopic = new sns.Topic(this, 'AlertTopic', {
      topicName:   'incident-agent-alerts',
      displayName: 'Incident Agent Alerts',
    });

    // ─────────────────────────────────────────────────────────
    // SQS (P2 승인 게이트 — Step Functions waitForTaskToken)
    // ─────────────────────────────────────────────────────────

    const approvalDlq = new sqs.Queue(this, 'ApprovalDlq', {
      queueName:         'incident-approval-dlq',
      retentionPeriod:   cdk.Duration.days(14),
      encryption:        sqs.QueueEncryption.SQS_MANAGED,
    });

    const approvalQueue = new sqs.Queue(this, 'ApprovalQueue', {
      queueName:         'incident-approval',
      visibilityTimeout: cdk.Duration.seconds(3600),
      encryption:        sqs.QueueEncryption.SQS_MANAGED,
      deadLetterQueue: {
        queue:           approvalDlq,
        maxReceiveCount: 1,
      },
    });

    // ─────────────────────────────────────────────────────────
    // 공통 Lambda 설정
    // ─────────────────────────────────────────────────────────

    const commonEnv: Record<string, string> = {
      AWS_ACCOUNT_ID:    this.account,
      INCIDENT_TABLE:    incidentTable.tableName,
      RUNBOOK_TABLE:     runbookTable.tableName,
      ALERT_TOPIC_ARN:   alertTopic.topicArn,
      APPROVAL_QUEUE_URL: approvalQueue.queueUrl,
      BEDROCK_MODEL_ID:  'anthropic.claude-sonnet-4-5',
      SLACK_WEBHOOK_URL: process.env.SLACK_WEBHOOK_URL ?? '',
      APPROVAL_DEFAULT_DECISION: process.env.APPROVAL_DEFAULT_DECISION ?? 'reject',
    };

    const lambdaDefaults = {
      runtime:      lambda.Runtime.PYTHON_3_11,
      architecture: lambda.Architecture.ARM_64,
      timeout:      cdk.Duration.minutes(5),
      memorySize:   512,
      environment:  commonEnv,
    };

    // logRetention 은 deprecated (legacy Custom::LogRetention 리소스 생성).
    // 함수별 전용 LogGroup 을 명시적으로 만들어 logGroup 으로 주입한다.
    const makeLogGroup = (id: string): logs.LogGroup =>
      new logs.LogGroup(this, `${id}LogGroup`, {
        retention:     logs.RetentionDays.ONE_MONTH,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      });
    const projectRoot = path.join(__dirname, '../..');
    const lambdaCode = lambda.Code.fromAsset(projectRoot, {
      bundling: {
        image: lambda.Runtime.PYTHON_3_11.bundlingImage,
        local: {
          tryBundle(outputDir: string): boolean {
            const { execSync } = require('child_process');
            try {
              execSync(`pip install -r ${projectRoot}/requirements-lambda.txt -t ${outputDir} --quiet`);
              execSync(`mkdir -p ${outputDir}/src`);
              execSync(`cp -r ${projectRoot}/src/agents ${outputDir}/src/agents`);
              execSync(`cp -r ${projectRoot}/src/step_functions ${outputDir}/src/step_functions`);
              execSync(`cp ${projectRoot}/src/__init__.py ${outputDir}/src/__init__.py 2>/dev/null || true`);
              return true;
            } catch {
              return false;
            }
          },
        },
        command: ['bash', '-c', 'pip install -r /asset-input/requirements-lambda.txt -t /asset-output && mkdir -p /asset-output/src && cp -r /asset-input/src/agents /asset-output/src/agents && cp -r /asset-input/src/step_functions /asset-output/src/step_functions && cp /asset-input/src/__init__.py /asset-output/src/__init__.py 2>/dev/null || true'],
        platform: 'linux/arm64',
      },
      exclude: [
        '.env',
        '.env.*',
        '.git',
        '.git/**',
        '.harness',
        '.harness/**',
        '.mypy_cache',
        '.mypy_cache/**',
        '.pytest_cache',
        '.pytest_cache/**',
        '.ruff_cache',
        '.ruff_cache/**',
        '.venv',
        '.venv/**',
        '__pycache__',
        '**/__pycache__/**',
        '*.pyc',
        'src/stacks/cdk.out',
        'src/stacks/cdk.out/**',
        'src/stacks/dist',
        'src/stacks/dist/**',
        'src/stacks/node_modules',
        'src/stacks/node_modules/**',
      ],
    });

    // ─────────────────────────────────────────────────────────
    // [1] Detector Lambda
    // ─────────────────────────────────────────────────────────

    const detectorRole = new iam.Role(this, 'DetectorRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    detectorRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'logs:StartQuery',
        'logs:GetQueryResults',
        'logs:DescribeLogGroups',
      ],
      resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:*`],
    }));
    detectorRole.addToPolicy(new iam.PolicyStatement({
      actions: ['xray:GetTraceSummaries', 'xray:BatchGetTraces'],
      resources: ['*'],
    }));
    detectorRole.addToPolicy(new iam.PolicyStatement({
      actions: ['cloudwatch:GetMetricStatistics', 'cloudwatch:ListMetrics'],
      resources: ['*'],
    }));

    const detectorFn = new lambda.Function(this, 'DetectorFunction', {
      ...lambdaDefaults,
      functionName: 'incident-agent-detector',
      handler:      'src.agents.operations.detector.handler.lambda_handler',
      code:         lambdaCode,
      role:         detectorRole,
      logGroup:     makeLogGroup('DetectorFunction'),
      description:  'Incident Agent — Detector: CW Logs Insights + X-Ray',
    });

    // ─────────────────────────────────────────────────────────
    // [2] Analyzer Lambda
    // ─────────────────────────────────────────────────────────

    const analyzerRole = new iam.Role(this, 'AnalyzerRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    analyzerRole.addToPolicy(new iam.PolicyStatement({
      actions:   ['bedrock:InvokeModel'],
      resources: [`arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-sonnet-4-5`],
    }));
    incidentTable.grantReadData(analyzerRole);

    const analyzerFn = new lambda.Function(this, 'AnalyzerFunction', {
      ...lambdaDefaults,
      functionName: 'incident-agent-analyzer',
      handler:      'src.agents.operations.analyzer.handler.lambda_handler',
      code:         lambdaCode,
      role:         analyzerRole,
      logGroup:     makeLogGroup('AnalyzerFunction'),
      timeout:      cdk.Duration.minutes(3),
      description:  'Incident Agent — Analyzer: Bedrock LLM root-cause + severity',
    });

    // ─────────────────────────────────────────────────────────
    // [3] Decision Lambda
    // ─────────────────────────────────────────────────────────

    const decisionRole = new iam.Role(this, 'DecisionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    runbookTable.grantReadData(decisionRole);

    const decisionFn = new lambda.Function(this, 'DecisionFunction', {
      ...lambdaDefaults,
      functionName: 'incident-agent-decision',
      handler:      'src.agents.operations.decision.handler.lambda_handler',
      code:         lambdaCode,
      role:         decisionRole,
      logGroup:     makeLogGroup('DecisionFunction'),
      description:  'Incident Agent — Decision: runbook selection + AUTO/APPROVE/MANUAL',
    });

    // ─────────────────────────────────────────────────────────
    // Approval Bridge Lambda
    // ─────────────────────────────────────────────────────────

    const approvalBridgeRole = new iam.Role(this, 'ApprovalBridgeRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    approvalBridgeRole.addToPolicy(new iam.PolicyStatement({
      actions: ['states:SendTaskSuccess', 'states:SendTaskFailure'],
      resources: ['*'],
    }));
    approvalRequestTable.grantReadWriteData(approvalBridgeRole);

    const approvalBridgeFn = new lambda.Function(this, 'ApprovalBridgeFunction', {
      ...lambdaDefaults,
      functionName: 'incident-agent-approval-bridge',
      handler:      'src.agents.operations.approval_bridge.handler.lambda_handler',
      code:         lambdaCode,
      role:         approvalBridgeRole,
      logGroup:     makeLogGroup('ApprovalBridgeFunction'),
      timeout:      cdk.Duration.minutes(1),
      environment: {
        ...commonEnv,
        APPROVAL_REQUEST_TABLE: approvalRequestTable.tableName,
        SLACK_SIGNING_SECRET: process.env.SLACK_SIGNING_SECRET ?? '',
        APPROVAL_REQUEST_TTL_SEC: process.env.APPROVAL_REQUEST_TTL_SEC ?? '86400',
      },
      description:  'Incident Agent — Approval bridge: Slack interactive approval to Step Functions callback',
    });
    approvalQueue.grantConsumeMessages(approvalBridgeFn);
    approvalBridgeFn.addEventSource(new lambdaEventSources.SqsEventSource(approvalQueue, {
      batchSize: 1,
    }));
    const approvalBridgeUrl = approvalBridgeFn.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
    });

    // ─────────────────────────────────────────────────────────
    // Runbook seed custom resource
    // ─────────────────────────────────────────────────────────

    const runbookSeedRole = new iam.Role(this, 'RunbookSeedRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    runbookTable.grantReadWriteData(runbookSeedRole);

    const runbookSeedFn = new lambda.Function(this, 'RunbookSeedFunction', {
      ...lambdaDefaults,
      functionName: 'incident-agent-runbook-seed',
      handler: 'src.agents.operations.runbook_seed.handler.lambda_handler',
      code: lambdaCode,
      role: runbookSeedRole,
      logGroup: makeLogGroup('RunbookSeedFunction'),
      timeout: cdk.Duration.minutes(1),
      description: 'Incident Agent — seed built-in capability-based runbooks',
    });

    const runbookSeedProvider = new cr.Provider(this, 'RunbookSeedProvider', {
      onEventHandler: runbookSeedFn,
    });

    new cdk.CustomResource(this, 'RunbookSeed', {
      serviceToken: runbookSeedProvider.serviceToken,
      properties: {
        TableName: runbookTable.tableName,
        CatalogVersion: '2026-04-12',
      },
    });

    // ─────────────────────────────────────────────────────────
    // [4] Executor Lambda
    // ─────────────────────────────────────────────────────────

    const executorRole = new iam.Role(this, 'ExecutorRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    // SSM Automation — 특정 문서만 허용
    executorRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ssm:StartAutomationExecution', 'ssm:GetAutomationExecution'],
      resources: [
        `arn:aws:ssm:${this.region}:${this.account}:automation-definition/AWS-Restart*`,
        `arn:aws:ssm:${this.region}:${this.account}:automation-definition/AWS-Scale*`,
        `arn:aws:ssm:${this.region}:${this.account}:automation-definition/AWS-Increase*`,
        `arn:aws:ssm:${this.region}:${this.account}:automation-definition/AWS-Create*`,
        `arn:aws:ssm:${this.region}:${this.account}:automation-definition/AWS-SendSlack*`,
      ],
    }));
    incidentTable.grantWriteData(executorRole);

    const executorFn = new lambda.Function(this, 'ExecutorFunction', {
      ...lambdaDefaults,
      functionName: 'incident-agent-executor',
      handler:      'src.agents.operations.executor.handler.lambda_handler',
      code:         lambdaCode,
      role:         executorRole,
      logGroup:     makeLogGroup('ExecutorFunction'),
      timeout:      cdk.Duration.minutes(10),
      description:  'Incident Agent — Executor: SSM + Slack report + DynamoDB record',
    });

    // ─────────────────────────────────────────────────────────
    // Step Functions — Operations 파이프라인 상태 머신
    // ─────────────────────────────────────────────────────────

    const operationsStateMachineRole = new iam.Role(this, 'StateMachineRole', {
      assumedBy: new iam.ServicePrincipal('states.amazonaws.com'),
    });
    operationsStateMachineRole.addToPolicy(new iam.PolicyStatement({
      actions:   ['lambda:InvokeFunction'],
      resources: [
        detectorFn.functionArn,
        analyzerFn.functionArn,
        decisionFn.functionArn,
        executorFn.functionArn,
      ],
    }));
    operationsStateMachineRole.addToPolicy(new iam.PolicyStatement({
      actions:   ['sns:Publish'],
      resources: [alertTopic.topicArn],
    }));
    operationsStateMachineRole.addToPolicy(new iam.PolicyStatement({
      actions:   ['sqs:SendMessage'],
      resources: [approvalQueue.queueArn],
    }));

    const sfnLogGroup = new logs.LogGroup(this, 'StateMachineLogGroup', {
      logGroupName:  '/aws/states/incident-agent-pipeline',
      retention:     logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const operationsDefinitionBody = sfn.DefinitionBody.fromString(
      JSON.stringify(
        this.buildStateMachineDefinition('pipeline.json', {
          DetectorFunctionArn: detectorFn.functionArn,
          AnalyzerFunctionArn: analyzerFn.functionArn,
          DecisionFunctionArn: decisionFn.functionArn,
          ExecutorFunctionArn: executorFn.functionArn,
          AlertTopicArn: alertTopic.topicArn,
          ApprovalQueueUrl: approvalQueue.queueUrl,
        })
      )
    );

    const operationsStateMachine = new sfn.StateMachine(this, 'IncidentPipeline', {
      stateMachineName: 'incident-agent-pipeline',
      definitionBody: operationsDefinitionBody,
      role:             operationsStateMachineRole,
      tracingEnabled:   true,
      logs: {
        destination:        sfnLogGroup,
        level:              sfn.LogLevel.ERROR,
        includeExecutionData: true,
      },
    });

    // ─────────────────────────────────────────────────────────
    // EventBridge — CloudWatch Alarm 상태 변경 → Step Functions
    // ─────────────────────────────────────────────────────────

    const ebRole = new iam.Role(this, 'EventBridgeRole', {
      assumedBy: new iam.ServicePrincipal('events.amazonaws.com'),
    });
    ebRole.addToPolicy(new iam.PolicyStatement({
      actions:   ['states:StartExecution'],
      resources: [operationsStateMachine.stateMachineArn],
    }));

    new events.Rule(this, 'AlarmStateChangeRule', {
      ruleName:    'incident-agent-alarm-trigger',
      description: 'CloudWatch Alarm ALARM 상태 → 인시던트 파이프라인 실행',
      eventPattern: {
        source:     ['aws.cloudwatch'],
        detailType: ['CloudWatch Alarm State Change'],
        detail: {
          state: { value: ['ALARM'] },
        },
      },
      targets: [
        new targets.SfnStateMachine(operationsStateMachine, {
          role: ebRole,
        }),
      ],
    });

    // ─────────────────────────────────────────────────────────
    // [5] Provisioning Lambda
    // ─────────────────────────────────────────────────────────

    const provisioningTable = new dynamodb.Table(this, 'ProvisioningPlans', {
      tableName: 'provisioning-plans',
      partitionKey: { name: 'plan_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const provisioningArtifactBucket = new s3.Bucket(this, 'ProvisioningArtifacts', {
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const provisioningRole = new iam.Role(this, 'ProvisioningRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    provisioningTable.grantReadWriteData(provisioningRole);
    provisioningRole.addToPolicy(new iam.PolicyStatement({
      actions: ['sns:Publish'],
      resources: [alertTopic.topicArn],
    }));

    const provisioningFn = new lambda.Function(this, 'ProvisioningFunction', {
      ...lambdaDefaults,
      functionName: 'incident-agent-provisioning',
      handler:      'src.agents.provisioning.handler.lambda_handler',
      code:         lambdaCode,
      role:         provisioningRole,
      logGroup:     makeLogGroup('ProvisioningFunction'),
      environment: {
        ...commonEnv,
        PROVISIONING_TABLE: provisioningTable.tableName,
        PROVISIONING_COST_AUTO_LIMIT_USD: '200',
      },
      description:  'Platform Agent — Provisioning: blueprint + IAM plan + cost estimate',
    });

    const provisioningArtifactWriterRole = new iam.Role(this, 'ProvisioningArtifactWriterRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    provisioningArtifactBucket.grantPut(provisioningArtifactWriterRole);
    provisioningTable.grantWriteData(provisioningArtifactWriterRole);

    const provisioningArtifactWriterFn = new lambda.Function(this, 'ProvisioningArtifactWriterFunction', {
      ...lambdaDefaults,
      functionName: 'platform-agent-provisioning-artifact-writer',
      handler: 'src.agents.provisioning.artifact_writer.lambda_handler',
      code: lambdaCode,
      role: provisioningArtifactWriterRole,
      logGroup: makeLogGroup('ProvisioningArtifactWriterFunction'),
      timeout: cdk.Duration.minutes(1),
      environment: {
        ...commonEnv,
        PROVISIONING_TABLE: provisioningTable.tableName,
        PROVISIONING_ARTIFACT_BUCKET: provisioningArtifactBucket.bucketName,
        PROVISIONING_ARTIFACT_PREFIX: 'plans',
      },
      description: 'Platform Agent — Provisioning: persist generated CDK artifacts to S3',
    });

    // ─────────────────────────────────────────────────────────
    // [6] Deployment Validation Lambda
    // ─────────────────────────────────────────────────────────

    const deploymentRole = new iam.Role(this, 'DeploymentRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    deploymentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['cloudwatch:GetMetricStatistics', 'cloudwatch:ListMetrics'],
      resources: ['*'],
    }));
    deploymentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['sns:Publish'],
      resources: [alertTopic.topicArn],
    }));

    const deploymentFn = new lambda.Function(this, 'DeploymentFunction', {
      ...lambdaDefaults,
      functionName: 'incident-agent-deployment',
      handler:      'src.agents.deployment.handler.lambda_handler',
      code:         lambdaCode,
      role:         deploymentRole,
      logGroup:     makeLogGroup('DeploymentFunction'),
      description:  'Platform Agent — Deployment: smoke tests + canary analysis + rollback decision',
    });

    const deploymentRollbackRole = new iam.Role(this, 'DeploymentRollbackRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    deploymentRollbackRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ssm:StartAutomationExecution'],
      resources: [
        `arn:${cdk.Aws.PARTITION}:ssm:${this.region}:${this.account}:automation-definition/*:*`,
        `arn:${cdk.Aws.PARTITION}:ssm:${this.region}::automation-definition/*:*`,
      ],
    }));

    const deploymentRollbackFn = new lambda.Function(this, 'DeploymentRollbackFunction', {
      ...lambdaDefaults,
      functionName: 'platform-agent-deployment-rollback',
      handler: 'src.agents.deployment.rollback_executor.lambda_handler',
      code: lambdaCode,
      role: deploymentRollbackRole,
      logGroup: makeLogGroup('DeploymentRollbackFunction'),
      timeout: cdk.Duration.minutes(1),
      description: 'Platform Agent — Deployment: execute rollback automation or emit manual rollback plan',
    });

    // ─────────────────────────────────────────────────────────
    // Step Functions — Provisioning / Deployment 상태 머신
    // ─────────────────────────────────────────────────────────

    const provisioningStateMachineRole = new iam.Role(this, 'ProvisioningStateMachineRole', {
      assumedBy: new iam.ServicePrincipal('states.amazonaws.com'),
    });
    provisioningStateMachineRole.addToPolicy(new iam.PolicyStatement({
      actions: ['lambda:InvokeFunction'],
      resources: [provisioningFn.functionArn, provisioningArtifactWriterFn.functionArn],
    }));
    provisioningStateMachineRole.addToPolicy(new iam.PolicyStatement({
      actions: ['sns:Publish'],
      resources: [alertTopic.topicArn],
    }));
    provisioningStateMachineRole.addToPolicy(new iam.PolicyStatement({
      actions: ['sqs:SendMessage'],
      resources: [approvalQueue.queueArn],
    }));
    const provisioningSfnLogGroup = new logs.LogGroup(this, 'ProvisioningStateMachineLogGroup', {
      logGroupName: '/aws/states/platform-agent-provisioning',
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const provisioningDefinitionBody = sfn.DefinitionBody.fromString(
      JSON.stringify(
        this.buildStateMachineDefinition('provisioning.json', {
          ProvisioningFunctionArn: provisioningFn.functionArn,
          ProvisioningArtifactWriterArn: provisioningArtifactWriterFn.functionArn,
          AlertTopicArn: alertTopic.topicArn,
          ApprovalQueueUrl: approvalQueue.queueUrl,
        })
      )
    );

    const provisioningStateMachine = new sfn.StateMachine(this, 'ProvisioningPipeline', {
      stateMachineName: 'platform-agent-provisioning',
      definitionBody: provisioningDefinitionBody,
      role: provisioningStateMachineRole,
      tracingEnabled: true,
      logs: {
        destination: provisioningSfnLogGroup,
        level: sfn.LogLevel.ERROR,
        includeExecutionData: true,
      },
    });

    const deploymentStateMachineRole = new iam.Role(this, 'DeploymentStateMachineRole', {
      assumedBy: new iam.ServicePrincipal('states.amazonaws.com'),
    });
    deploymentStateMachineRole.addToPolicy(new iam.PolicyStatement({
      actions: ['lambda:InvokeFunction'],
      resources: [deploymentFn.functionArn, deploymentRollbackFn.functionArn],
    }));
    deploymentStateMachineRole.addToPolicy(new iam.PolicyStatement({
      actions: ['sns:Publish'],
      resources: [alertTopic.topicArn],
    }));
    deploymentStateMachineRole.addToPolicy(new iam.PolicyStatement({
      actions: ['sqs:SendMessage'],
      resources: [approvalQueue.queueArn],
    }));
    const deploymentSfnLogGroup = new logs.LogGroup(this, 'DeploymentStateMachineLogGroup', {
      logGroupName: '/aws/states/platform-agent-deployment',
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const deploymentDefinitionBody = sfn.DefinitionBody.fromString(
      JSON.stringify(
        this.buildStateMachineDefinition('deployment.json', {
          DeploymentFunctionArn: deploymentFn.functionArn,
          DeploymentRollbackFunctionArn: deploymentRollbackFn.functionArn,
          AlertTopicArn: alertTopic.topicArn,
          ApprovalQueueUrl: approvalQueue.queueUrl,
        })
      )
    );

    const deploymentStateMachine = new sfn.StateMachine(this, 'DeploymentPipeline', {
      stateMachineName: 'platform-agent-deployment',
      definitionBody: deploymentDefinitionBody,
      role: deploymentStateMachineRole,
      tracingEnabled: true,
      logs: {
        destination: deploymentSfnLogGroup,
        level: sfn.LogLevel.ERROR,
        includeExecutionData: true,
      },
    });

    // ─────────────────────────────────────────────────────────
    // [7] Generic ingress (HTTP/direct → EventBridge custom events)
    // ─────────────────────────────────────────────────────────

    const ingressRole = new iam.Role(this, 'IngressRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    ingressRole.addToPolicy(new iam.PolicyStatement({
      actions: ['events:PutEvents'],
      resources: [`arn:aws:events:${this.region}:${this.account}:event-bus/default`],
    }));

    const ingressFn = new lambda.Function(this, 'IngressFunction', {
      ...lambdaDefaults,
      functionName: 'platform-agent-ingress',
      handler: 'src.agents.ingress.handler.lambda_handler',
      code: lambdaCode,
      role: ingressRole,
      logGroup: makeLogGroup('IngressFunction'),
      timeout: cdk.Duration.minutes(1),
      environment: {
        ...commonEnv,
        EVENT_BUS_NAME: 'default',
        INGRESS_EVENT_SOURCE: 'platform-agent.api',
      },
      description: 'Platform Agent — Ingress: HTTP/direct requests into EventBridge',
    });
    const ingressFnUrl = ingressFn.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
    });

    // ─────────────────────────────────────────────────────────
    // [8] Runtime Router ingress (custom EventBridge events)
    // ─────────────────────────────────────────────────────────

    const routerRole = new iam.Role(this, 'RouterRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    routerRole.addToPolicy(new iam.PolicyStatement({
      actions: ['states:StartExecution'],
      resources: [
        provisioningStateMachine.stateMachineArn,
        deploymentStateMachine.stateMachineArn,
      ],
    }));

    const routerFn = new lambda.Function(this, 'RouterFunction', {
      ...lambdaDefaults,
      functionName: 'platform-agent-router',
      handler: 'src.agents.router.handler.lambda_handler',
      code: lambdaCode,
      role: routerRole,
      logGroup: makeLogGroup('RouterFunction'),
      timeout: cdk.Duration.minutes(1),
      environment: {
        ...commonEnv,
        PROVISIONING_STATE_MACHINE_ARN: provisioningStateMachine.stateMachineArn,
        DEPLOYMENT_STATE_MACHINE_ARN: deploymentStateMachine.stateMachineArn,
      },
      description: 'Platform Agent — Router: EventBridge ingress to provisioning and deployment pipelines',
    });

    new events.Rule(this, 'PlatformRequestRouterRule', {
      ruleName: 'platform-agent-request-router',
      description: 'Normalized provisioning/deployment requests routed into Step Functions',
      eventPattern: {
        source: ['platform-agent', 'platform-agent.api', 'platform-agent.slack', 'platform-agent.github', 'platform-agent.jira'],
        detailType: ['Provisioning Request', 'Deployment Validation Request'],
      },
      targets: [new targets.LambdaFunction(routerFn)],
    });

    // ─────────────────────────────────────────────────────────
    // [9] Reporting Lambda + EventBridge schedules
    // ─────────────────────────────────────────────────────────

    const reportingRole = new iam.Role(this, 'ReportingRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });
    incidentTable.grantReadData(reportingRole);
    reportingRole.addToPolicy(new iam.PolicyStatement({
      actions: ['cloudwatch:GetMetricStatistics', 'cloudwatch:ListMetrics'],
      resources: ['*'],
    }));

    const reportingFn = new lambda.Function(this, 'ReportingFunction', {
      ...lambdaDefaults,
      functionName: 'incident-agent-reporting',
      handler:      'src.agents.operations.reporting.handler.lambda_handler',
      code:         lambdaCode,
      role:         reportingRole,
      logGroup:     makeLogGroup('ReportingFunction'),
      timeout:      cdk.Duration.minutes(3),
      description:  'Platform Agent — Reporting: daily SLO / weekly on-call / monthly capacity',
    });

    // Daily SLO report — every day at 08:00 KST (23:00 UTC)
    new events.Rule(this, 'DailySloSchedule', {
      ruleName:    'platform-agent-daily-slo',
      description: 'Daily SLO burn-rate report',
      schedule:    events.Schedule.cron({ minute: '0', hour: '23' }),
      targets: [
        new targets.LambdaFunction(reportingFn, {
          event: events.RuleTargetInput.fromObject({ report_type: 'daily_slo' }),
        }),
      ],
    });

    // Weekly on-call report — every Monday at 09:00 KST (00:00 UTC)
    new events.Rule(this, 'WeeklyOncallSchedule', {
      ruleName:    'platform-agent-weekly-oncall',
      description: 'Weekly on-call MTTR and incident summary',
      schedule:    events.Schedule.cron({ minute: '0', hour: '0', weekDay: 'MON' }),
      targets: [
        new targets.LambdaFunction(reportingFn, {
          event: events.RuleTargetInput.fromObject({ report_type: 'weekly_oncall' }),
        }),
      ],
    });

    // Monthly capacity report — 1st of each month at 09:00 KST (00:00 UTC)
    new events.Rule(this, 'MonthlyCapacitySchedule', {
      ruleName:    'platform-agent-monthly-capacity',
      description: 'Monthly capacity headroom and cost-optimisation report',
      schedule:    events.Schedule.cron({ minute: '0', hour: '0', day: '1' }),
      targets: [
        new targets.LambdaFunction(reportingFn, {
          event: events.RuleTargetInput.fromObject({ report_type: 'monthly_capacity' }),
        }),
      ],
    });

    // ─────────────────────────────────────────────────────────
    // CloudFormation Outputs
    // ─────────────────────────────────────────────────────────

    new cdk.CfnOutput(this, 'StateMachineArn', {
      value:      operationsStateMachine.stateMachineArn,
      exportName: 'IncidentAgentStateMachineArn',
      description: 'Step Functions 파이프라인 ARN',
    });
    new cdk.CfnOutput(this, 'ProvisioningStateMachineArn', {
      value: provisioningStateMachine.stateMachineArn,
      exportName: 'PlatformAgentProvisioningStateMachineArn',
      description: 'Provisioning Step Functions 파이프라인 ARN',
    });
    new cdk.CfnOutput(this, 'ProvisioningArtifactBucketName', {
      value: provisioningArtifactBucket.bucketName,
      exportName: 'PlatformAgentProvisioningArtifactBucketName',
      description: 'Provisioning CDK artifact bundle S3 bucket',
    });
    new cdk.CfnOutput(this, 'DeploymentStateMachineArn', {
      value: deploymentStateMachine.stateMachineArn,
      exportName: 'PlatformAgentDeploymentStateMachineArn',
      description: 'Deployment validation Step Functions 파이프라인 ARN',
    });
    new cdk.CfnOutput(this, 'IngressFunctionUrl', {
      value: ingressFnUrl.url,
      exportName: 'PlatformAgentIngressFunctionUrl',
      description: 'Generic ingress Function URL for provisioning/deployment requests',
    });
    new cdk.CfnOutput(this, 'RouterFunctionArn', {
      value: routerFn.functionArn,
      exportName: 'PlatformAgentRouterFunctionArn',
      description: 'Runtime router Lambda ARN for provisioning/deployment ingress',
    });
    new cdk.CfnOutput(this, 'AlertTopicArn', {
      value:      alertTopic.topicArn,
      exportName: 'IncidentAgentAlertTopicArn',
    });
    new cdk.CfnOutput(this, 'ApprovalQueueUrl', {
      value:      approvalQueue.queueUrl,
      exportName: 'IncidentAgentApprovalQueueUrl',
    });
    new cdk.CfnOutput(this, 'ApprovalRequestTableName', {
      value:      approvalRequestTable.tableName,
      exportName: 'IncidentAgentApprovalRequestTableName',
    });
    new cdk.CfnOutput(this, 'ApprovalBridgeFunctionUrl', {
      value:      approvalBridgeUrl.url,
      exportName: 'IncidentAgentApprovalBridgeFunctionUrl',
      description: 'Slack interactive approval Request URL',
    });
    new cdk.CfnOutput(this, 'IncidentTableName', {
      value:      incidentTable.tableName,
      exportName: 'IncidentAgentIncidentTableName',
    });
    if (vercelDashboardRole) {
      new cdk.CfnOutput(this, 'VercelDashboardRoleArn', {
        value: vercelDashboardRole.roleArn,
        exportName: 'PlatformAgentVercelDashboardRoleArn',
        description: 'OIDC role ARN for the Vercel read-only dashboard incident feed',
      });
    }
    new cdk.CfnOutput(this, 'ProvisioningFunctionArn', {
      value:      provisioningFn.functionArn,
      exportName: 'PlatformAgentProvisioningFunctionArn',
    });
    new cdk.CfnOutput(this, 'DeploymentFunctionArn', {
      value:      deploymentFn.functionArn,
      exportName: 'PlatformAgentDeploymentFunctionArn',
    });
    new cdk.CfnOutput(this, 'ReportingFunctionArn', {
      value:      reportingFn.functionArn,
      exportName: 'PlatformAgentReportingFunctionArn',
    });
  }

  // ─────────────────────────────────────────────────────────
  // Step Functions 정의 빌더
  // pipeline.json 의 ${Placeholder} 를 실제 값으로 치환
  // ─────────────────────────────────────────────────────────

  private buildStateMachineDefinition(
    fileName: string,
    replacements: Record<string, string>,
  ): object {
    const fs   = require('fs');
    const path = require('path');
    let substituted = fs.readFileSync(
      path.join(__dirname, `../step_functions/${fileName}`), 'utf-8'
    );

    for (const [placeholder, value] of Object.entries(replacements)) {
      substituted = substituted.replace(
        new RegExp(`\\$\\{${placeholder}\\}`, 'g'),
        value,
      );
    }

    return JSON.parse(substituted);
  }
}
