terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }

  # Configure a real backend per environment; local state is fine for a demo.
  # backend "s3" {
  #   bucket = "feaststore-tfstate"
  #   key    = "feaststore/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "feaststore"
      ManagedBy = "terraform"
      Env       = var.environment
    }
  }
}
