# Terraform Spawn GCP Compute Instance

This project is a simple Terraform configuration for creating a compute
instance in Google Cloud Platform (GCP).

## Project Structure

The project is composed of the following files:

- `main.tf`: Contains the main Terraform resources and data used in this project, including the compute instance, network configurations, local ssh keys, GCP provider and required services, and user information.
- `variables.tf`: Defines the necessary input variables for the Terraform configuration.
- `outputs.tf`: Defines the outputs that will be shown after Terraform completes its operations.
- `ssh_scripts/tfssh`: A bash script for ssh'ing into the created instance.
- `ssh_scripts/tfreceive`: A bash script for receiving files from the created instance.
- `ssh_scripts/tfsend`: A bash script for sending files to the created instance.

## Prerequisites

- You need to have Terraform installed on your machine.
- You should have a GCP account, a project, and a service account with appropriate permissions. Also, a JSON key file for your service account is required.
- Make sure the firewall settings in your GCP project allow SSH connections.

## Usage

1. First, clone this repository to your local machine using `git clone`.

2. Create a `.tfvars` file to configure with your data.

3. `terraform init`.

4. `terraform plan`.

5. `terraform apply`

6. You can SSH into the created instance using the `tfssh` script in the `ssh_scripts` directory.

7. You can use the `tfsend` and `tfreceive` scripts in the `ssh_scripts` directory to send and receive files to/from the created instance.

## Variables

The variables defined in the `variables.tf` file:

- `region`: The region where the resources will be created.
- `zone`: The specific zone within the region where the resources will be created.
- `credentials_file`: Path to the credentials file in JSON format.
- `project`: Your GCP project name.
- `machine_type`: GCP machine type to be used for the instances.

## Outputs

The `outputs.tf` file defines the following outputs:

- `external_ip`: The external IP of the created instance.
- `instance_id`: The ID of the created instance.
- `gcp_user_name`: The username to be used for SSH connections to the instance.
