#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { RegistryPlannerStack } from '../registry_planner_stack';

const app = new cdk.App();
function required(key: string): string {
  const value = app.node.tryGetContext(key);
  if (typeof value !== 'string' || !value) throw new Error(`Missing context: ${key}`);
  return value;
}
new RegistryPlannerStack(app, 'RegistryPlannerStack', {
  env: { account: required('plannerAccount'), region: required('plannerRegion') },
  assetPath: required('plannerAssetPath'), usersTableArn: required('plannerUsersTableArn'),
  repository: required('plannerRepository'), branch: required('plannerBranch'),
  vercelTeam: required('vercelTeamSlug'), vercelProject: required('vercelProjectName'),
  oidcProviderArn: required('vercelOidcProviderArn'),
});
