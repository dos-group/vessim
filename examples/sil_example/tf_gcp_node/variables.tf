variable "region" {
  description = "The region where the resources will be created"
  type        = string
  default     = "europe-west3"
}

variable "zone" {
  description = "the specific zone within the region where the resources will be created."
  type        = string
  default     = "europe-west3-c"
}

variable "credentials_file" {
  description = "path to the credentials file in JSON format."
  type        = string
}

variable "project" {
  description = "Your gcp project name."
  type        = string
}

#
variable "machine_type" {
  description = "gcp machine type to be used for the instances."
  type        = string
  default     = "e2-standard-2"
}
