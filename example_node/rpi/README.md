## RPI Node Setup

```
ssh pi@raspberrypi
sudo apt update && sudo apt upgrade
sudo apt install git vim python3-pip i2c-tools
git clone https://github.com/dos-group/vessim/
cp vessim/example_node/ .
rm -rf vessim
cd example_node/rpi
sudo pip install -r requirements.txt
sudo sh init.sh
sudo reboot
```
