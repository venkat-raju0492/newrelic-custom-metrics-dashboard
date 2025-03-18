variable "environment" {
  description = "The name of the environment"
}

variable "project" {
  description = "The name of the project"
}

variable "region" {
  description = "AWS region"
}

variable "lambda_s3_bucket" {
    description = "lambda s3 bucket"
}

variable "lambda_timeout" {
  description = "lambda timeout"
}

variable "lambda_memory_size" {
  description = "Lambda memory size"
}

variable "newrelic_transfer_ver" {
  description = "Version of the New Relic metrics transfer"
  type        = string
}

variable "retention_in_days" {
  description = "Number of days to retain logs in CloudWatch"
  type        = number
  default     = 30
}

variable "new_relic_api_key" {
  description = "New Relic API key"
}

variable "new_relic_api_url" {
  description = "New Relic API URL"
}

variable "lambda_layer_s3_key" {
  description = "The S3 key for the Lambda layer ZIP file"
  type        = string
}