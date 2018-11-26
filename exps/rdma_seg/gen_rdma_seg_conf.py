#!/usr/bin/python

import os
import sys
import yaml

sys.path.insert(0, os.path.abspath('..'))
from rone_exp_common import *

RUNS = range(3)
FRAMEWORKS = [RoNE, RoCE]
VERBS = [READ_RC]
SEG_SIZES = [2**x for x in range(10, 23, 2)]
SIGNAL_IFREQ = [2**x for x in range(0, 7, 2)]

base_config = {
    'expname': 'rdma_seg_cpu',
    #'run': <x>,
    #'outf': <x>,

    'runlen': 10,
    'cpus': [0],
    'rhost': '10.10.1.1',
    'clients': ['10.10.1.1'],
    
    #'framework': <x>,
    #'seg_size': <x>
    #'verb': <x>,
}

def gen_base_outfname(config):
    if config['framework'] == RoCE:
        base_name = '%s.%s.%s.%dseg.%dsig.%d.yaml' % \
            (config['expname'], config['framework'], config['verb'],
             config['seg_size'], config['signal_ifreq'], config['run'])
    else:
        base_name = '%s.%s.%s.%dseg.%d.yaml' % \
            (config['expname'], config['framework'], config['verb'],
             config['seg_size'], config['run'])
    return base_name

def output_config(config):
    config_fname = 'conf/' + gen_base_outfname(config)
    with open(config_fname, 'w') as configf:
        yaml.dump(config, configf)

def get_rdma_seg_config(framework, verb, seg_size, signal_ifreq, run):
    config = base_config.copy()
    config['framework'] = framework
    config['verb'] = verb
    config['seg_size'] = seg_size
    if framework == RoCE:
        config['signal_ifreq'] = signal_ifreq
    config['run'] = run
    config['outf'] = os.path.abspath('results/') + \
        '/res.' + gen_base_outfname(config)
    return config

def main():
    for framework in FRAMEWORKS:
        for verb in VERBS:
            for seg_size in SEG_SIZES:
                for signal_ifreq in SIGNAL_IFREQ:
                    for run in RUNS:
                        # Get the config
                        config = get_rdma_seg_config(framework, verb, seg_size,
                            signal_ifreq, run)

                        # Output the config
                        output_config(config)

if __name__ == '__main__':
    main()
