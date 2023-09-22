# VESSIM Node API Server

This repository contains an API server designed to run on different types of
nodes, specifically tailored for a Raspberry Pi and a Linux node. The project
is designed to be integrated into the VESSIM environment.

## Description

The API server is implemented as two distinct classes - `RpiNodeApiServer` and
`VirtualNodeApiServer` - both inheriting from the abstract `FastApiServer`
class.

The `RpiNodeApiServer` is specifically tailored for a Raspberry Pi, using
dynamic voltage and frequency scaling (DVFS) for power management, while the
`VirtualNodeApiServer` is designed to run on a Linux node, using `cpulimit` for
process CPU usage limitation. Both implementations allow the control of power
modes via API calls.

## Setup
### Raspberry Pi Node Setup

For setting up the project on a Raspberry Pi, follow the below instructions:

1. SSH into your Raspberry Pi:
```bash
ssh pi@raspberrypi
```

2. Update and upgrade your Pi:
```bash
sudo apt update && sudo apt upgrade
```

3. Install necessary dependencies:
```bash
sudo apt install git vim python3-pip i2c-tools
```

4. Clone the repository:
```bash
git clone https://github.com/dos-group/vessim/
```

5. Navigate to the `rpi` directory and install the Python dependencies:
```bash
cd vessim/examples/sil_example/example_node/rpi
sudo pip install -r requirements.txt
```

6. Execute initialization script:
```bash
sudo sh init.sh
```

7. Reboot your Raspberry Pi:
```bash
sudo reboot
```

### Virtual Node Setup

This section provides instructions on how to set up a virtual node and how 
to define the infrastructure configuration for your Google Cloud Platform (GCP) compute instance using the open-source infrastructure as code (IaC) tool [Terraform](https://www.terraform.io/).

#### Prerequisites

- A GCP account, project, and service account with appropriate permissions 
are necessary.
- A JSON key file for your service account is required.
- [Install Terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli)

#### Setup

1. First, clone this repository to your local machine:
```bash
git clone https://github.com/dos-group/vessim/
```

2. Navigate to the `tf_gcp_node` directory:
```bash
cd vessim/examples/sil_example/tf_gcp_node
```

3. Create a `.tfvars` file to configure with your data. 
	
4. Run `terraform init`

5. Run `terraform plan`

6. Run `terraform apply`

	To access the GCP instance, you can use SSH by running the `tfssh script` located in the `ssh_scripts` directory. 
	Moreover, if you want to transfer files to or from the instance, you can use the `tfsend` and `tfreceive` scripts in the `ssh_scripts` directory.

### Variables
The variables defined in the `variables.tf` file:

- region: The region where the resources will be created.
- zone: The specific zone within the region where the resources will be created.
- credentials_file: Path to the credentials file in JSON format.
- project: Your GCP project name.
- machine_type: GCP machine type to be used for the instances.

### Outputs

The `outputs.tf` file defines the following outputs that will be shown 
after Terraform completes its operations:

- `external_ip`: The external IP of the created instance.
- `instance_id`: The ID of the created instance.
- `gcp_user_name`: The username to be used for SSH connections to the 
instance.

## Usage

Once installed and set up, the API server is started.
It will listen for incoming HTTP requests on the defined 
host and port.

The server provides access to the following endpoints:

- `PUT /power_mode`: Set the power mode for the server. The available 
power modes are `power-saving`, `normal`, and `high performance`.
- `GET /power_mode`: Retrieve the current power mode of the server.
- `GET /power`: Retrieve the current power usage of the node.