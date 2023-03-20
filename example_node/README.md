## RPI Node Setup

```
ssh pi@raspberrypi
sudo apt update && sudo apt upgrade
sudo apt install git vim python3-pip i2c-tools
sudo pip install smbus psutil cpufreq pi-ina219
git clone https://github.com/opsengine/cpulimit.git
cd cpulimit; make; sudo cp src/cpulimit /usr/bin; cd ..; rm -rf cpulimit
git clone https://github.com/dos-group/vessim/
sudo sh vessim/example_node/init.sh
sudo reboot
```

The installation of PyTorch and Torchvision on Raspberry Pi via `pip` is not
possible as the package is not compiled for the Pi's architecture. However,
PyTorch and Torchvision can be installed on Raspberry Pi by compiling it
manually or by using a pre-built wheel. For more detailed instructions on the
installation process, please refer to the following resource:
https://qengineering.eu/install-pytorch-on-raspberry-pi-4.html.


Base workload to run on a client

1. Install the requirements: `pip3 install -r requirements.txt`
2. Run the PyTorch training script in the background: `python pytorch_training.py &`
    - Via `jobs` you can list background jobs and retrieve them via `fg`
3. Store PID of the last executed process in variable: `pytorch=$!`

TODO:
- `cpulimit`?
- Measure CPU usage of process?
  - e.g. `top -b -n 2 -d 1 -p $pytorch | tail -1 | awk '{print $9}'` (https://stackoverflow.com/a/52751050/5373209)

