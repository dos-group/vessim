#!/bin/bash

apt-get update
apt-get install python3-pip git sysbench -y
cd /opt
git clone --depth 1 https://github.com/dos-group/vessim.git
cp -r vessim/examples/sil/example_node vessim_node_api_server
rm -rf vessim
cd vessim_node_api_server/virtual_node
pip3 install -r requirements.txt
python3 v_node_api_server.py