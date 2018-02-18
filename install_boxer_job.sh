#!/bin/sh

cd src/supervisor/jobs/boxer
chmod +x install_darknet.sh
rm -fr darknet
./install_darknet.sh
