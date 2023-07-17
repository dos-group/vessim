variable "region" {
  description = "The region where the resources will be created"
  type        = string
  default     = "eu-central-1"
}

variable "ami" {
  description = "Amazon Machine Image (AMI), different for every region!"
  type        = string
  default     = "ami-0ab1a82de7ca5889c"
}

variable "profile" {
  description = "Your AWS profile name."
  type        = string
  default     = "default"
}

variable "instance_type" {
  description = "AWS instance type to be used for the instances."
  type        = string
  default     = "t2.micro"
}
