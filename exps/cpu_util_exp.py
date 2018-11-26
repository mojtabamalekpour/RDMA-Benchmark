#!/usr/bin/python

import argparse
import os
import paramiko
import platform
import subprocess
import yaml

#XXX: DEBUG
import random

from rone_exp_common import *
from time import sleep

if 'HW2_HOME' in os.environ:
    rone_code_dir = os.environ['HW2_HOME']
else:
    print 'HW2_HOME must be defined!'
    sys.exit(1)

# Default config
CPU_EXP_CONFIG_DEFAULTS = {
    # Experiment naming config
    'run': 1,
    'expname': None,
    'outf': None,

    # Experiment parameters
    'runlen': 5,
    'cpus': [0],
    'server': '10.10.1.2',

    #'framework': DCTCP,
    'framework': RoNE,
    #'framework': RoCE,
    'verb': READ_RC,
    'polling': False,

    #'seg_size': 1024,
    #'seg_size': (1024 * 64),
    'seg_size': (1024 * 16),

    'window_size': (64 * 1024),
    #'window_size': (128 * 1024),

    'signal_ifreq': 1,
    'numqps': 1,

    # Cluster specific config
    'mlx_devstr': 'mlx4_0',
    'line_rate': 10e9,
    'vlans': [267, 268],
    'priorities': [5, 6],
    'username': 'Mojtaba',
    'rone_code_dir': rone_code_dir,
    'iface': IFACE,
    'iperf_baseport': 5001,
    'rone_baseport': 55282,
    'rone_ibaseport': 54282,
    'roce_baseport': 53282,
}

class CpuUtilExpConfig(object):
    def __init__(self, *initial_data, **kwargs):
        #TODO: defaults?
        for key in CPU_EXP_CONFIG_DEFAULTS:
            setattr(self, key, CPU_EXP_CONFIG_DEFAULTS[key])
        for dictionary in initial_data:
            for key in dictionary:
                if not hasattr(self, key):
                    print 'WARNING! Unexpected attr: %s' % key
                setattr(self, key, dictionary[key])
        for key in kwargs:
            if not hasattr(self, key):
                print 'WARNING! Unexpected attr: %s' % key
            setattr(self, key, kwargs[key])

def run_cpu_util_exp(config):
    # Connect to the remote host
    config.server_ssh = connect_rhost(config.server, config)
    config.client_sshs = [connect_rhost(c, config) for c in config.clients]

    # Configure both of the servers
    ## Or maybe just ensure that the configuration is correct?
    print 'Warning! Skipping server configuration!'

    #if config.verb == WRITE_UC:
    #    config.timeout = 40
    config.timeout = 30

    # Start the server on the remote host (after killing it)
    kill_framework_servers(config)
    rhost_servers = start_framework_servers(config, 1)

    # Start the local client
    clients = start_framework_clients(config)

    #XXX: HACK
    if config.verb == WRITE_UC:
        #assert(config.framework == iRoCE or config.framework == RoNE)
        assert(config.framework == iRoCE or config.framework == RoNE or config.framework == DCTCP)
        #clients['servers'] = rhost_servers

    # Measure CPU on both the local and remote host 
    server_dstat_proc = start_rhost_dstat_proc(config, config.server_ssh, config.runlen)
    client_dstat_proc = start_rhost_dstat_proc(config, config.client_sshs[0], config.runlen)

    # Wait
    sleep(config.runlen)

    # Process the CPU results
    server_cpu_results = process_rhost_dstat_proc(server_dstat_proc)
    client_cpu_results = process_rhost_dstat_proc(client_dstat_proc)

    # Process the network results
    network_results = process_framework_clients_output(config, clients)
    #XXX: Hack because roce_incast_* and rone_incast* do not terminate!
    #network_results = None 

    # Aggregate the results
    if config.verb == READ_RC or config.verb == WRITE_RC:
        results = {
            'server_cpu': client_cpu_results,
            'client_cpu': server_cpu_results,
            'network': network_results,
        }
    else:
        results = {
            'server_cpu': server_cpu_results,
            'client_cpu': client_cpu_results,
            'network': network_results,
        }

    # Output the results
    print yaml.dump(results)
    if config.outf:
        with open(config.outf, 'w') as outf:
            yaml.dump(results, outf)

    # Cleanup
    kill_framework_servers(config)

    #XXX: DEBUG
    #for server in rhost_servers:
    #    stdin, stdout, stderr = server
    #    print 'Server DEBUG:'
    #    print stdout.read(), stderr.read()

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Measure the CPU utilization '
        'of the Linux TCP stack (DCTCP)')
    parser.add_argument('--configs', help='Configuration files to use. '
        'The configuration format is unsurprisingly not documented.',
        nargs='+')
    parser.add_argument('--skip-existing', help='Skip experiments if the '
        'results already exist.', action='store_true')
    args = parser.parse_args()

    # Get the config
    if args.configs:
        #random.shuffle(args.configs)
        for fi, config_fname in enumerate(args.configs):
            with open(config_fname) as configf:
                user_config = yaml.load(configf)

            print 'config_fname:', config_fname
            try:
                config = CpuUtilExpConfig(user_config)
            except:
                print 'Failed config:', yaml.dump(user_config)
                raise

            config.rone_baseport += 2 * fi
            config.rone_ibaseport += 2 * fi
            config.roce_baseport += 2 * fi

            if config.outf and os.path.exists(config.outf) and \
                    args.skip_existing:
                print 'Skipping experiment because output file \'%s\' exists!' % \
                    config.outf
            else:
                sleep(0.5)
                run_cpu_util_exp(config)
    else:
        # Run an experiment with the default config
        user_config = {}
        config = CpuUtilExpConfig(user_config)
        run_cpu_util_exp(config)

if __name__ == '__main__':
    main()
