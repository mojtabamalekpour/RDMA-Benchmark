#!/bin/bash

dir=`pwd`

cd ..
#sudo ./cpu_util_exp.py --skip-existing --configs $dir/conf/*.yaml

# Other invocations
#sudo ./cpu_util_exp.py --skip-existing --configs $dir/conf/*1024seg*.yaml
#sudo ./cpu_util_exp.py --skip-existing --configs $dir/conf/*RoNE*.yaml
sudo ./cpu_util_exp.py --skip-existing --configs $dir/conf/*RoCE*.yaml
