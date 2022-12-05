
variable "environment" {
  description = "The Deployment environment"
}


variable "region" {
  description = "The AWS region"
}

variable "vpc_id" {
  description = "The id of the vpc where this application will run"
}

variable "subnets" {
  description = "List of subnets where this application will run"
  type        = list(any)
}
# the type is any, as the subnets are terraform resources

variable "docker_version" {
  description = "The version of the docker that should be used"
}
