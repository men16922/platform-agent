import type { Deployment } from "./mock-data";

export function deploymentDuration(deployment: Deployment): string {
  if (deployment.duration_sec === undefined) return "Not measured";
  const seconds = `${deployment.duration_sec.toFixed(1)}s`;
  return deployment.duration_scope ? `${seconds} run` : seconds;
}
