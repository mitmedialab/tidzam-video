#!/bin/sh
# Install basic packages

#remove previous
rm -fr darknet

#update
echo 'Updating system...'
sudo apt-get update -y
sudo apt-get install python3-pip git -y
sudo pip3 install numpy matplotlib scipy pillow 

#install darknet
echo 'Installing darknet...'
git clone https://github.com/pjreddie/darknet
cp MakefileDarknet darknet/Makefile

cd darknet
echo 'Compilling darknet...'
make


touch __init__.py
mkdir weights
cd weights
echo 'Downloading weights...'
sudo wget https://pjreddie.com/media/files/yolo9000.weights
sudo wget https://pjreddie.com/media/files/tiny-yolo-voc.weights

cd ../..

echo 'Installing darket and boxer scripts...'
cp darknet.py ./darknet
cp boxerjob.py ./darknet
cp boxer.py ./darknet


