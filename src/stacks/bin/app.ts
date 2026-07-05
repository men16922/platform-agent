#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { IncidentAgentStack } from '../incident_agent_stack';

const app = new cdk.App();

new IncidentAgentStack(app, 'IncidentAgentStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region:  process.env.CDK_DEFAULT_REGION ?? 'ap-northeast-2',
  },
  description: 'platform-agent — provision → validate deploys → operate incidents',
});
