# Add secruity group for API

resource "aws_security_group" "api-sg" {
  name        = "api-site-${var.environment}-sg"
  description = "API security group to allow inbound/outbound traffic"
  vpc_id      = var.vpc_id

  ingress {
    from_port = "80"
    to_port   = "80"
    protocol  = "tcp"
    self      = true
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  tags = {
    Environment = "${var.environment}"
  }
}
