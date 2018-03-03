#!/bin/sh
export PATH=/usr/local/cuda-9.0/bin${PATH:+:${PATH}}
export LD_LIBRARY_PATH=/usr/local/cuda-9.0/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}

apt-get install libopencv-dev python-opencv

cd src/supervisor/jobs/boxer
chmod +x install_darknet.sh
rm -fr darknet
./install_darknet.sh
