environment     = "staging"
project = "poc"
region  = "us-west-2"
lambda_s3_bucket    = "aretifactory-s3-bucket"

lambda_timeout = 900
lambda_memory_size = 1024
retention_in_days = 30

new_relic_api_key = ""
new_relic_api_url = "https://metric-api.newrelic.com/metric/v1"

lambda_layer_s3_key = "<s3 path for lamabda layers>/<zip file name>"