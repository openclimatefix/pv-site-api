# create s3 bucket for application verions

resource "aws_s3_bucket" "eb" {
  bucket = "nowcasting-eb-api-sites-${var.environment}"
}

resource "aws_s3_bucket_object" "eb-object" {
  bucket = aws_s3_bucket.eb.id
  key    = "beanstalk/docker-compose-${var.docker_version}.yml"
  source = "${path.module}/docker-compose.yml"
}

resource "aws_s3_bucket_public_access_block" "eb-pab" {
  bucket = aws_s3_bucket.eb.id

  block_public_acls       = true
  block_public_policy     = true
  restrict_public_buckets = true
  ignore_public_acls      = true

}
