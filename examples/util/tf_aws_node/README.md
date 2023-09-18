# Terraform Spawn AWS EC2 Instance

This project is a simple Terraform configuration for creating an Amazon Web services (AWS) EC2 instance.

## Project Structure

The project is composed of the following files:

- `main.tf`: Contains the main Terraform resources and data used in this project, including the aws instance, network configurations, local ssh keys, AWS provider and required services, and user information.
- `variables.tf`: Defines the necessary input variables for the Terraform configuration.
- `outputs.tf`: Defines the outputs that will be shown after Terraform completes its operations.
- `ssh_scripts/tfssh`: A bash script for ssh'ing into the created instance.
- `ssh_scripts/tfreceive`: A bash script for receiving files from the created instance.
- `ssh_scripts/tfsend`: A bash script for sending files to the created instance.

## Prerequisites

- You need to have Terraform installed on your machine.
- You should have an AWS account with appropriate permissions and configured AWS authentication locally.

## Usage

1. First, clone this repository to your local machine using `git clone`.

2. `terraform init`.

3. `terraform plan`.

4. `terraform apply`

5. You can SSH into the created instance using the `tfssh` script in the `ssh_scripts` directory.

7. You can use the `tfsend` and `tfreceive` scripts in the `ssh_scripts` directory to send and receive files to/from the created 6nstance.

## Variables

The variables defined in the `variables.tf` file:

- `region`: The region where the resources will be created.
- `ami`: Amazon Machine Image (AMI), different for every region!
- `profile`: Your AWS profile name.
- `instance_type`: AWS instance type to be used for the instances.

## Outputs

The `outputs.tf` file defines the following outputs:

- `public_ip`: The public IP of the created instance.
- `instance_id`: The ID of the created instance.
