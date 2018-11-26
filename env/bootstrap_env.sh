#!/bin/bash

# Setup keys
cp keys/id_rsa ~/.ssh/
cat keys/id_rsa.pub >> ~/.ssh/authorized_keys

# Ensure that ssh works without asking for Authenticity to be accepted
## TODO: for hosts: ssh-keyscan $host >> ~/.ssh/known_hosts
SERVERS="node-0 node-1 localhost 127.0.0.1 10.10.1.1 10.10.1.2"
for h in $SERVERS; do
    ssh-keyscan -H $h >> ~/.ssh/known_hosts
done

# Setup env variable for the git repo
cd ..
HW2_HOME=`pwd`
echo "export HW2_HOME=$HW2_HOME" >> ~/.bashrc

# Install ansible
sudo apt-get install -y software-properties-common
sudo apt-add-repository -y ppa:ansible/ansible
sudo apt-get update
sudo apt-get install -y ansible
