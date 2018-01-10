#!/bin/sh
# Install basic packages
export BASE_INSTALL=`dirname $0`
sudo apt-get update -y
sudo apt-get install python3-pip git -y
sudo pip3 install numpy matplotlib scipy

# Install PeachPy and confu
sudo pip3 install --upgrade git+https://github.com/Maratyszcza/PeachPy
sudo pip3 install --upgrade git+https://github.com/Maratyszcza/confu

# Install Ninja
git clone https://github.com/ninja-build/ninja.git
cd ninja
git checkout release
./configure.py --bootstrap
export NINJA_PATH=$PWD

cd ..

# Install clang
sudo apt-get install clang -y

# Install NNPACK-darknet
git clone https://github.com/thomaspark-pkj/NNPACK-darknet.git
cd NNPACK-darknet
confu setup
python3 ./configure.py --backend auto
$NINJA_PATH/ninja
sudo cp -a lib/* /usr/lib/
sudo cp include/nnpack.h /usr/include/
sudo cp deps/pthreadpool/include/pthreadpool.h /usr/include/

cd ..

# Uncomment for opencv
#cd $BASE_INSTALL
#chmod +x install-opencv_darkflow.sh
#bash install-opencv_darkflow.sh

# Build darknet-nnpack
git clone https://github.com/thomaspark-pkj/darknet-nnpack.git
sudo cp Makefile darknet-nnpack
cd darknet-nnpack
make

mkdir weights
cd weights
sudo wget https://pjreddie.com/media/files/yolo9000.weights
sudo wget https://pjreddie.com/media/files/tiny-yolo-voc.weights

cd ../..
