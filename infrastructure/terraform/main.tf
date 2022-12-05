module "api" {
  source = "./api"

  region                              = var.region
  environment                         = var.environment
  vpc_id                              = var.vpc_id
  subnets                             = var.public_subnets
  docker_version                      = var.api_version
}