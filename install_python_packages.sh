#!/bin/sh

sudo apt-get update -y
sudo apt-get install python3-pip git -y
sudo pip3 install numpy matplotlib scipy pillow django channels==1.1.6
sudo pip install git+https://github.com/dpallot/simple-websocket-server.git
