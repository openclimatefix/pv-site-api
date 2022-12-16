terraform {
 backend "s3" {
   bucket         = "sbri-terraform"
   key            = "state/terraform.tfstate"
   region         = "eu-west-2"
   encrypt        = true
 }
}