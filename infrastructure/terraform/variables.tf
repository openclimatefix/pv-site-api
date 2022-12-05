variable "region" {
  description = "The AWS region to use"
}

variable "environment" {
  description = "The Deployment environment"
}


variable "api_version" {
  description = "The API version"
}

variable "vpc_id" {
  description = "The VPC that is deployed"
}

variable "public_subnets" {
  description = "The public subnets for the vpc"
}
