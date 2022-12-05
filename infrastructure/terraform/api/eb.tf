# Creates various objects to do with elastic beanstalk (EB)
# 1. EB Application
# 2. EB Environment
# 3. EB application version
# 4. Application version gets deployed to environment using docker compose file


resource "aws_elastic_beanstalk_application" "eb-api-application" {
  name        = "nowcasting-api-sites-${var.environment}"
  description = "Site API for SBRI"
}

resource "aws_elastic_beanstalk_environment" "eb-api-env" {
  name        = "nowcasting-api-sites-${var.environment}"
  application = aws_elastic_beanstalk_application.eb-api-application.name
  cname_prefix = "nowcasting-api-sites-${var.environment}"
  version_label = "nowcasting-api-sites-${var.docker_version}"

  setting {
    namespace = "aws:autoscaling:launchconfiguration"
    name      = "InstanceType"
    value     = "t3.small"
  }

  # the next line IS NOT RANDOM,
#  see https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/concepts.platforms.html
  solution_stack_name = "64bit Amazon Linux 2 v3.4.16 running Docker"

  # There are a LOT of settings, see here for the basic list:
  # https://is.gd/vfB51g
  # This should be the minimally required set for Docker.

#  setting {
#    namespace = "aws:elasticbeanstalk:application:environment"
#    name      = "DB_URL"
#    value     = var.database_forecast_secret_url
#  }


  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "ORIGINS"
    value     = "*" #TODO change
  }

  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "API_VERSION"
    value     = var.docker_version
  }

  setting {
    namespace = "aws:ec2:vpc"
    name      = "VPCId"
    value     = var.vpc_id
  }
  setting {
    namespace = "aws:ec2:vpc"
    name      = "Subnets"
    #    value     = "${join(",", var.subnets)}"
    #    value     = var.subnets
    value    = var.subnets[0]
    resource = ""
  }
  setting {
    namespace = "aws:autoscaling:launchconfiguration"
    name      = "SecurityGroups"
    value     = aws_security_group.api-sg.id
  }
  setting {
    namespace = "aws:autoscaling:launchconfiguration"
    name      = "IamInstanceProfile"
    value     = aws_iam_instance_profile.ec2.arn
  }
  setting {
    namespace = "aws:elasticbeanstalk:environment"
    name      = "ServiceRole"
    value     = aws_iam_role.api-service-role.arn
  }

  setting {
    namespace = "aws:autoscaling:asg"
    name      = "MinSize"
    value     = "1"
  }
  setting {
    namespace = "aws:autoscaling:asg"
    name      = "MaxSize"
    value     = "1"
  }

  ###=========================== Logging ========================== ###

  setting {
    namespace = "aws:elasticbeanstalk:cloudwatch:logs"
    name      = "StreamLogs"
    value     = "true"
    resource  = ""
  }

  setting {
    namespace = "aws:elasticbeanstalk:cloudwatch:logs"
    name      = "DeleteOnTerminate"
    value     = "false"
    resource  = ""
  }

  setting {
    namespace = "aws:elasticbeanstalk:cloudwatch:logs"
    name      = "RetentionInDays"
    value     = "7"
    resource  = ""
  }

  setting {
    namespace = "aws:elasticbeanstalk:cloudwatch:logs:health"
    name      = "HealthStreamingEnabled"
    value     = "true"
    resource  = ""
  }

  setting {
    namespace = "aws:elasticbeanstalk:cloudwatch:logs:health"
    name      = "DeleteOnTerminate"
    value     = "false"
    resource  = ""
  }

  setting {
    namespace = "aws:elasticbeanstalk:cloudwatch:logs:health"
    name      = "RetentionInDays"
    value     = "7"
    resource  = ""
  }

    # make sure that when the application is made, the latest version is deployed to it
  provisioner "local-exec" {
    command = join("", ["aws elasticbeanstalk update-environment ",
      "--region ${var.region} ",
      "--application-name ${aws_elastic_beanstalk_application.eb-api-application.name} ",
      "--version-label ${aws_elastic_beanstalk_application_version.latest.name} ",
      "--environment-name ${aws_elastic_beanstalk_environment.eb-api-env.name}"
    ])
  }

}

resource "aws_elastic_beanstalk_application_version" "latest" {
  name        = "nowcasting-api-sites-${var.docker_version}"
  application = aws_elastic_beanstalk_application.eb-api-application.name
  description = "application version created by terraform (${var.docker_version})"
  bucket      = aws_s3_bucket.eb.id
  key         = aws_s3_bucket_object.eb-object.id

}
