#!/bin/bash

## pi config

# adjust access
chmod 755 ./config/rc.local
chmod 755 ./config/config.txt
# execute config scripts
cp ./config/rc.local /etc/rc.local
cp ./config/config.txt /boot/config.txt
# enable i2c for INA219 use
echo "i2c-dev" | sudo tee /etc/modules

## vessim api server setup

# define a project root path
PROJ_PATH=$(pwd)

# copy the project to /root
echo "Copying project to /root..."
cp -r $PROJ_PATH /root/

# copy the node_api_server module to /root
echo "Copying node_api_server to /root/"
cp $PROJ_PATH/../node_api_server.py /root/

# change the permissions of the project
echo "Setting permissions..."
chown -R root:root /root/rpi
chmod 755 /root/rpi
chmod 755 /root/rpi/rpi_api_server.py

# write the systemd service file
echo "Creating the systemd service file..."
cat << EOF > /etc/systemd/system/rpi_api.service
[Unit]
Description=Raspberry Pi API server
After=network.target

[Service]
ExecStart=/usr/bin/python3 /root/rpi/rpi_api_server.py
WorkingDirectory=/root/rpi
StandardOutput=inherit
StandardError=inherit
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

# reload the systemd daemon
echo "Reloading systemd daemon..."
systemctl daemon-reload

# enable the service
echo "Enabling the service to start on boot..."
systemctl enable rpi_api.service

# starting the service
echo "Starting the service..."
systemctl start rpi_api.service

echo "Done."
