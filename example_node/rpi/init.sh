#!/bin/bash

# adjust access
chmod 755 ./config/rc.local
chmod 755 ./config/config.txt
# execute config scripts
cp ./config/rc.local /etc/rc.local
cp ./config/config.txt /boot/config.txt
# enable i2c for INA219 use
echo "i2c-dev" | sudo tee /etc/modules
