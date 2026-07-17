# IRSA for the Helm chart's ServiceAccount. The only AWS surface the shipped
# control plane consumes is the DynamoDB activity table (deploy_recorder with
# PLATFORM_ACTIVITY_TABLE) — so that is the only grant, scoped to the exact
# table + its indexes. No Resource:"*" (repo guardrail).

data "aws_caller_identity" "current" {}

locals {
  oidc_path          = replace(aws_iam_openid_connect_provider.eks.url, "https://", "")
  activity_table_arn = "arn:aws:dynamodb:${var.region}:${data.aws_caller_identity.current.account_id}:table/${var.activity_table_name}"
}

data "aws_iam_policy_document" "chart_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_path}:sub"
      values   = ["system:serviceaccount:${var.chart_namespace}:${var.chart_service_account}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_path}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "chart" {
  name               = "${var.name}-chart-irsa"
  assume_role_policy = data.aws_iam_policy_document.chart_assume.json
}

data "aws_iam_policy_document" "activity_table" {
  statement {
    sid = "ActivityTableReadWrite"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:UpdateItem",
      "dynamodb:Query",
    ]
    resources = [
      local.activity_table_arn,
      "${local.activity_table_arn}/index/*",
    ]
  }
}

resource "aws_iam_role_policy" "chart_activity" {
  name   = "activity-table"
  role   = aws_iam_role.chart.id
  policy = data.aws_iam_policy_document.activity_table.json
}
