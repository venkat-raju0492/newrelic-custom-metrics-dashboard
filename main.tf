terraform {
  backend "s3" {} 
}

provider "aws" {
  region = var.region
}

locals {
  log_group_name                            = "/aws/lambda/new-relic-metrics-transfer-${var.environment}"
  lambda_new_relic_metrics_transfer_s3_key  = "${var.project}/new-relic-metrics-transfer/new-relic-metrics-transfer-${var.deploy_ver}.zip"

  # Common tags to be assigned to all resources
  common_tags = {
    Project      = var.project
    Environment  = var.environment
    CreatedBy    = "Terraform"
    CostCategory = var.cost_category
  }
}

data "aws_caller_identity" "current" {}

resource "aws_cloudwatch_log_group" "lambda_log_group" {
  name              = local.log_group_name
  retention_in_days = var.retention_in_days
  tags              = local.common_tags
 
}

module "security" {
  source                              = "./modules/security"
  common_tags                         = local.common_tags
  environment                         = var.environment
  project                             = var.project
}

module "new-relic-metrics-transfer-lambda" {
  source                        = "git@github.com:venkat-raju0492/terraform-lambda.git?ref=v1.0.0"
  s3_bucket                     = var.lambda_s3_bucket
  s3_key                        = local.lambda_new_relic_metrics_transfer_s3_key
  function_name                 = "${var.project}-new-relic-metrics-transfer-${var.environment}"
  role                          = module.security.new-relic-metrics-transfer-lambda-role-arn
  handler                       = "lambda_function/lambda_function.lambda_handler"
  runtime                       = "python3.13"
  timeout                       = var.lambda_timeout
  memory_size                   = var.lambda_memory_size
  lambda_layers                        = [aws_lambda_layer_version.new_relic_metrics_transfer_layer.arn]

  env_vars = {
    env                         = var.environment
    NEW_RELIC_API_KEY           = var.new_relic_api_key
    NEW_RELIC_API_URL           = var.new_relic_api_url
  }

  common_tags                   = merge(local.common_tags, tomap({
                    deploy_version = local.lambda_new_relic_metrics_transfer_s3_key
  }))

  lambda_depends_on    = aws_cloudwatch_log_group.lambda_log_group
  
}

# Create the Lambda layer
resource "aws_lambda_layer_version" "new_relic_metrics_transfer_layer" {
  s3_bucket        = var.lambda_s3_bucket
  s3_key           = var.lambda_layer_s3_key
  layer_name       = "${var.project}-new-relic-metrics-transfer-layer-${var.environment}"
  compatible_runtimes = ["python3.13"]
  description      = "Lambda layer for New Relic Metrics Transfer"
}

resource "aws_cloudwatch_event_rule" "new_relic_metrics_transfer_event_rule_hourly" {
  name                = "${var.project}-new-relic-metrics-transfer-schedule-${var.environment}"
  description         = "Trigger Lambda function every hour"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "new_relic_metrics_transfer_invoke_lambda_event_p1" {
  rule      = aws_cloudwatch_event_rule.new_relic_metrics_transfer_event_rule_hourly.name
  target_id = "lambda_target_p1_${var.environment}"
  arn       = module.new-relic-metrics-transfer-lambda.lambda_function_arn

  input = jsonencode({
  "queryMetricList": [
    {
      "query": "fields @timestamp, @message, @logStream | filter @message like 'Wrote record successfully' and @message not like 'full-feed' | parse @message 'id=*} Wrote record successfully: topic * partition' as @connectorName,@topicName | stats count_distinct(@connectorName) as metricValue by bin(1h) as eventTimestamp",
      "metricName": "aws.ecs.service.CountPerHour_${var.environment}",
      "logGrpName": "/ecs/inventory-acc-kafka-connect/${var.environment}"
    },
    {
      "query": "fields @timestamp, @message, @logStream | filter @message like 'Wrote record successfully' and @message not like 'full-feed' | parse @message 'id=*} Wrote record successfully: topic * partition' as @connectorName,@topicName | stats count(*) as metricValue by bin(1h) as eventTimestamp",
      "metricName": "aws.ecs.dev.InvAccKafkaConnect.DeltaEventsProducedPerHour_${var.environment}",
      "logGrpName": "/ecs/inventory-acc-kafka-connect/${var.environment}"
    },
    {
        <add multiple queries as needed depending on the request lambda can handle>
    }
  ]
})
}

resource "aws_lambda_permission" "new_relic_metrics_transfer_lambda_allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = module.new-relic-metrics-transfer-lambda.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.new_relic_metrics_transfer_event_rule_hourly.arn
}