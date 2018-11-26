#!/usr/bin/python

import argparse
import json
import numpy
import os
import re
import scipy
import scipy.stats
import socket
import sys
import paramiko
import platform
import re
import subprocess
import yaml

FLOAT_DESC_STR = '[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?'

# Enumerations
RoNE = 'RoNE'
RoCE = 'RoCE'
iRoCE = 'iRoCE'
DCTCP = 'DCTCP'
TRANSPORTS = [RoNE, iRoCE, RoCE, DCTCP]

READ_RC = 'READ_RC'
READ_UC = 'READ_UC'
WRITE_RC = 'WRITE_RC'
WRITE_UC = 'WRITE_UC'
VERBS = [READ_RC, READ_UC, WRITE_RC, WRITE_UC]

def verb_to_app_transport(verb):
    VERB_TO_APP_TRANSPORT = {
        READ_RC: ('ib_read_bw', 'RC'),
        READ_UC: ('ib_read_bw', 'UC'),
        WRITE_RC: ('ib_write_bw', 'RC'),
        WRITE_UC: ('ib_write_bw', 'UC'),
    }
    return VERB_TO_APP_TRANSPORT[verb]

# Constant? This should be part of the config?
IFACE = 'eno1d1'

def numsegs_for_msgsize(config):
    num_segs =  (config.msg_size + (config.seg_size - 1)) / (config.seg_size)
    return num_segs

def numsegs_for_runlen(config):
    num_segs =  int(config.line_rate / (config.seg_size * 8) * (config.runlen + 1))

    MAX_SEGS = 100000000
    if num_segs > MAX_SEGS:
        print 'Too many segs: %d, reducing to %d' % (num_segs, MAX_SEGS)
        num_segs = MAX_SEGS

    return num_segs

def config_vlans(config, vlans, priorities):
    subprocess.check_call('sudo modprobe 8021q', shell=True)
    for i, vlan in enumerate(vlans):
        cmd = 'sudo ip link add link %s name %s.%d type vlan id %d' % \
            (config.iface, config.iface, vlan, vlan)
        print cmd
        subprocess.call(cmd, shell=True)
        ip3 = vlan - 200
        ip4 = int(platform.uname()[1].split('.')[0][-2:])
        cmd = 'sudo ifconfig %s.%d 10.10.%d.%d/24 up' % \
            (config.iface, vlan, ip3, ip4)
        subprocess.check_call(cmd, shell=True)
        for tci in range(8):
            cmd = 'sudo vconfig set_egress_map %s.%d %d %d' % \
                (config.iface, vlan, tci, priorities[i])
            subprocess.check_call(cmd, shell=True)

def config_dcb_ets(config):
    cmd = 'mlnx_qos -i %s -p 2,0,1,3,4,5,6,7 ' % config.iface
    cmd += '-s ets,ets,ets,ets,ets,ets,ets,ets '
    cmd += '-t 10,10,10,10,10,10,10,30'

    subprocess.check_call(cmd, shell=True)

def connect_rhost(rhost, config):
    rssh = paramiko.SSHClient()
    rssh.load_system_host_keys()
    rssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh_config = paramiko.SSHConfig()
    user_config_file = os.path.expanduser("~/.ssh/config")
    if os.path.exists(user_config_file):
        with open(user_config_file) as f:
            ssh_config.parse(f)

    cfg = {'hostname': rhost, 'username': config.username}
    user_config = ssh_config.lookup(cfg['hostname'])
    for k in ('hostname', 'username', 'port'):
        if k in user_config:
            cfg[k] = user_config[k]

    print 'cfg:', cfg

    rssh.connect(**cfg)

    return rssh

def get_percentile(data, percentile):
    return numpy.asscalar(scipy.stats.scoreatpercentile(data, percentile))

def get_cdf_data(runs):
    data = runs[:]
    data.sort()
    counts, edges = numpy.histogram(data, bins=100, normed=True)
    cdf = numpy.cumsum(counts)
    xs = edges[1:]
    ys = [x*(edges[1]-edges[0]) for x in cdf]

    xs = [numpy.asscalar(x) for x in xs]
    ys = [numpy.asscalar(y) for y in ys]
    return (xs, ys)

def start_stdout_dstat_proc(config, run_len):
    dstat_cmd = config.rone_code_dir + '/exps/monitorDstat.py --runlen %d' % \
        run_len
    print 'dstat_cmd:', dstat_cmd
    dstat_proc = subprocess.Popen(dstat_cmd, shell=True,
        stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    return dstat_proc

def process_dstat_output_common(utils):
    agg_cpu = []
    # Throw away the beginning
    for util_ival in utils[2:]:
        cpu_keys = [key for key in util_ival if re.match(r".*cpu.*", key)]
        cpu = sum([100.0 - util_ival[key]['idl'] for key in cpu_keys])
        agg_cpu.append(cpu)

    cpu_results = {'50p': get_percentile(agg_cpu, 50),
                   'avg': 1.0 * sum(agg_cpu) / len(agg_cpu),
                   'ivals': agg_cpu,
                   }
    return cpu_results

def process_dstat_output(dstat_proc):
    utils = yaml.load(dstat_proc.stdout)
    utils = utils[1:-1]
    cpu_results = process_dstat_output_common(utils)
    return cpu_results

def start_rhost_dstat_proc(config, rssh, run_len):
    dstat_cmd = config.rone_code_dir + '/exps/monitorDstat.py --runlen %d' % \
        run_len
    stdin, stdout, stderr = rssh.exec_command(dstat_cmd)
    return (stdin, stdout, stderr)

def process_rhost_dstat_proc(rhost_dstat_proc):
    stdin, stdout, stderr = rhost_dstat_proc

    # DEBUG
    #print stdout.read(), stderr.read()

    utils = yaml.load(stdout)
    cpu_results = process_dstat_output_common(utils)
    return cpu_results

def exec_cmd(cmd, rhost_ssh=None, timeout=None):
    if not rhost_ssh:
        proc = subprocess.Popen(cmd, shell=True,
            stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        return proc
    else:
        stdin, stdout, stderr = rhost_ssh.exec_command(cmd, timeout=timeout)
        return (stdin, stdout, stderr)

def get_proc_output(proc):
    if type(proc) == type(tuple()):
        return proc[1]
    else:
        return proc.stdout

def get_proc_err(proc):
    if type(proc) == type(tuple()):
        return proc[2]
    else:
        return proc.stderr

def kill_roce_servers(config):
    app, trans = verb_to_app_transport(config.verb)
    kill_cmd = 'sudo killall %s' % app
    stdin, stdout, stderr = config.server_ssh.exec_command(kill_cmd)
    #DEBUG
    print stdout.read(), stderr.read()

    if hasattr(config, 'client_sshs'):
        for client_ssh in config.client_sshs:
            if client_ssh:
                stdin, stdout, stderr = client_ssh.exec_command(kill_cmd)
                #DEBUG
                #print stdout.read(), stderr.read()


def kill_roce_incast_servers(config):
    kill_cmds = ['sudo killall roce_read_incast_write0',
        'sudo killall roce_write_incast_write0', 'sudo killall roce_read_incast']
    for kill_cmd in kill_cmds:
        stdin, stdout, stderr = config.server_ssh.exec_command(kill_cmd)
        #DEBUG
        print stdout.read(), stderr.read()
        for client_ssh in config.client_sshs:
            stdin, stdout, stderr = client_ssh.exec_command(kill_cmd)

def kill_rone_incast_servers(config):
    kill_cmds = ['sudo killall rone_read_incast',
        'sudo killall rone_write_incast_write0']
    for kill_cmd in kill_cmds:
        stdin, stdout, stderr = config.server_ssh.exec_command(kill_cmd)
        #DEBUG
        print stdout.read(), stderr.read()
        for client_ssh in config.client_sshs:
            stdin, stdout, stderr = client_ssh.exec_command(kill_cmd)

def kill_rone_servers(config):
    kill_cmd = 'sudo killall rone_read_rc' 
    stdin, stdout, stderr = config.server_ssh.exec_command(kill_cmd)

    #DEBUG
    print stdout.read(), stderr.read()

def kill_iperf3_servers(config):
    kill_cmd = 'sudo killall iperf3'
    stdin, stdout, stderr = config.server_ssh.exec_command(kill_cmd)

    #DEBUG
    print stdout.read(), stderr.read()

def kill_incast_servers(config):
    kill_cmd = 'sudo killall incast_server'
    stdin, stdout, stderr = config.server_ssh.exec_command(kill_cmd)

    #DEBUG
    print stdout.read(), stderr.read()

def get_roce_app_base_cmd(config, port):
    app, trans = verb_to_app_transport(config.verb)
    #TODO: Allow for RoCE apps to use either polling or blocking

    #assert(config.window_size >= config.seg_size)
    #if config.seg_size > config.window_size:
    #    config.window_size = config.seg_size
    #outstanding = config.window_size / config.seg_size #TODO: Round up instead?
    #assert(outstanding >= 1)

    # TODO: this could assume mlx_devstr == 'mlx4_0' if none is present
    if config.mlx_devstr == 'mlx4_0':
        mlx_devargs = '-d mlx4_0 -i 2' # Assumes CloudLab Utah
    elif config.mlx_devstr == 'mlx5_0':
        mlx_devargs = '-d mlx5_0 -i 1'
    else:
        raise ValueError('Unknown mlx_devstr')

    #XXX: HACK: -D for duration does not work with sleeping for events (-e)
    if config.polling:
        cmd = 'sudo %s -p %d %s -F -D %d -s %d -Q %d -l %d --report_gbits -c %s -q %d' % \
            (app, port, mlx_devargs, config.runlen + 2, config.seg_size, config.signal_ifreq, config.signal_ifreq, trans, config.numqps)
    else:
        if hasattr(config, 'msg_size'):
            numsegs = numsegs_for_msgsize(config)
        else:
            numsegs = numsegs_for_runlen(config)
        
        # It seems like "-n" is per QP to perftest? This is unclear.
        #if hasattr(config, 'numqps'):
        #    numsegs = numsegs / config.numqps
        numsegs = numsegs / config.numqps #/ config.signal_ifreq / outstanding
        #numsegs = (numsegs / 10 / 16) * 10 * 16
        #numsegs = (numsegs / config.signal_ifreq / outstanding) * config.signal_ifreq * outstanding
        #numsegs = max(numsegs, outstanding)
        print 'numsegs:', numsegs, 'config.signal_ifreq:', config.signal_ifreq#, 'outstanding:', outstanding

        cmd = 'time sudo %s -p %d -e %s -F -n %d -s %d -Q %d -l %d --report_gbits -c %s -q %d' % \
            (app, port, mlx_devargs, numsegs, config.seg_size, config.signal_ifreq, config.signal_ifreq, trans, config.numqps)

    return cmd

def start_roce_servers(config, numservers):
    procs = []
    #XXX: HACK/Work-around.  The congestion and tcp-friendliness experiments
    # assume that clients send data to the servers.  If it is the opposite, there
    # will not be any congestion.  In the case of READs, servers send data to
    # clients, so we have to reverse the meaning of server and clients.
    if config.verb == READ_RC or config.verb == READ_UC:
        for i, client_ssh in enumerate(config.client_sshs):
            port = config.roce_baseport + i
            cmd = get_roce_app_base_cmd(config, port)
            stdin, stdout, stderr = client_ssh.exec_command(cmd)
            procs.append((stdin, stdout, stderr))
    else:
        for port in [config.roce_baseport + i for i in range(numservers)]:
            cmd = get_roce_app_base_cmd(config, port)
            stdin, stdout, stderr = config.server_ssh.exec_command(cmd)
            procs.append((stdin, stdout, stderr))
    return procs

def start_rone_servers(config, numservers):
    procs = []
    for port in [config.rone_baseport + i for i in range(numservers)]:
        rone_server_loc = config.rone_code_dir + '/bin/rone_read_rc'
        #rone_server_cmd = 'sudo ' + rone_server_loc + ' -p %d' % config.rone_baseport
        rone_server_cmd = rone_server_loc + ' -p %d' % port
        print 'rone_server_cmd:', rone_server_cmd
        stdin, stdout, stderr = config.server_ssh.exec_command(rone_server_cmd)
        procs.append((stdin, stdout, stderr))
    return procs

def start_iperf3_servers(config, numservers):
    procs = []
    for port in [config.iperf_baseport + i for i in range(numservers)]:
        # TODO: run multiple per cores and set CPU affinity
        iperf_server_cmd = 'iperf3 -s -p %d' % port
        stdin, stdout, stderr = config.server_ssh.exec_command(iperf_server_cmd)
        procs.append((stdin, stdout, stderr))
    return procs

def start_roce_incast_servers(config, numservers):
    procs = []
    # For better synchronization, the senders of data in the incast program is
    # the servers
    for client_ssh in config.client_sshs:
        incast_loc = roce_incast_cmd(config)
        if config.verb == READ_RC:
            server_cmd = '%s -p %d -b %d' % (incast_loc, config.rone_baseport,
                config.rone_ibaseport)
        elif config.verb == WRITE_UC:
            numsegs = numsegs_for_msgsize(config)
            window_in_segs = config.window_size / config.seg_size
            server_cmd = '%s -p %d -b %d -n %d -m %d -e 1 -q %d' % (incast_loc,
                config.rone_baseport, config.rone_ibaseport, numsegs,
                config.seg_size, window_in_segs)

        print 'incast server cmd:', server_cmd
        if hasattr(config, 'timeout'):
            timeout = config.timeout
        else:
            timeout = None
        print 'timeout:', timeout
        stdin, stdout, stderr = client_ssh.exec_command(server_cmd,
            timeout=timeout)
        procs.append((stdin, stdout, stderr))
    return procs

def start_rone_incast_servers(config, numservers):
    procs = []
    # For better synchronization, the senders of data in the incast program is
    # the servers
    for client_ssh in config.client_sshs:
        incast_loc = rone_incast_cmd(config)
        if hasattr(config, 'ratelimit') and not config.ratelimit:
            ratelimit_str = '-R 0 '
        else:
            ratelimit_str = ''
        if config.verb == READ_RC:
            server_cmd = '%s -p %d -b %d %s' % (incast_loc, config.rone_baseport,
                config.rone_ibaseport, ratelimit_str)
        elif config.verb == WRITE_UC:
            numsegs = numsegs_for_msgsize(config)
            window_in_segs = config.window_size / config.seg_size
            server_cmd = '%s -p %d -b %d %s -n %d -m %d -e 1 ' % (incast_loc,
                config.rone_baseport, config.rone_ibaseport, ratelimit_str,
                numsegs, config.seg_size)
        print 'incast server cmd:', server_cmd
        if hasattr(config, 'timeout'):
            timeout = config.timeout
        else:
            timeout = None
        print 'timeout:', timeout

        proc = exec_cmd(server_cmd, client_ssh, timeout=timeout)
        procs.append(proc)

        #stdin, stdout, stderr = client_ssh.exec_command(server_cmd,
        #    timeout=timeout)
        #procs.append((stdin, stdout, stderr))
    return procs

def start_incast_servers(config, numservers):
    procs = []
    # For better synchronization, the senders of data in the incast program is
    # the servers
    for client_ssh in config.client_sshs:
        incast_loc = config.rone_code_dir + '/bin/incast/incast_server'
        server_cmd = '%s %d' % (incast_loc, config.iperf_baseport)
        print 'incast server cmd:', server_cmd
        stdin, stdout, stderr = client_ssh.exec_command(server_cmd)
        procs.append((stdin, stdout, stderr))
    return procs

    #XXX: Old code
    #for port in [config.iperf_baseport + i for i in range(numservers)]:
    #    incast_loc = config.rone_code_dir + '/bin/incast/incast_server'
    #    server_cmd = '%s %d' % (incast_loc, port)
    #    stdin, stdout, stderr = config.server_ssh.exec_command(server_cmd)
    #    procs.append((stdin, stdout, stderr))
    #return procs

def start_roce_clients_read(config):
    procs = []
    for (offset, cip) in enumerate(config.clients):
        port = config.roce_baseport + offset
        cmd = get_roce_app_base_cmd(config, port) + ' %s' % cip
        print 'RoCE cmd:', cmd
        timeout = None
        if hasattr(config, 'timeout'):
            timeout = config.timeout
        proc = exec_cmd(cmd, config.server_ssh, timeout)
        procs.append(proc)
    return procs

def start_roce_clients(config, offset, rhost):
    # TODO: run multiple per cores and set CPU affinity
    port = config.roce_baseport + offset
    cmd = get_roce_app_base_cmd(config, port) + ' %s' % config.server
    print 'RoCE cmd:', cmd
    timeout = None
    if hasattr(config, 'timeout'):
        timeout = config.timeout
    proc = exec_cmd(cmd, rhost, timeout)
    return [proc]

def start_rone_clients(config):
    # TODO: run multiple per cores and set CPU affinity
    rone_client_loc = config.rone_code_dir + '/bin/rone_read_rc'
    numsegs = numsegs_for_runlen(config)
    #cmd_template = 'sudo ' + rone_client_loc + ' -h %s -c 1 -n %d -p %d -m %d'
    cmd_template = rone_client_loc + ' -h %s -c 1 -n %d -p %d -m %d'
    cmd = cmd_template % (config.server, numsegs, config.rone_baseport,
        config.seg_size)
    print 'RoNE cmd:', cmd
    proc = exec_cmd(cmd, rhost)
    return [proc]

def start_iperf3_clients(config, offset, rhost):
    # TODO: run multiple per cores and set CPU affinity

    #XXX: I'm bad at python
    #iperf3_cmd_template = 'iperf3 -c %{rhost}s -t %{runlen}d -p %{port}d -J -Z -l 1M'
    #iperf3_config = {'rhost': config.rhost, 'runlen': config.runlen + 2,
    #    'port': config.iperf_baseport}

    if hasattr(config, 'msg_size'):
        mstr = '-n %d' % config.msg_size
    else:
        mstr = '-t %d' % (config.runlen + 2)

    iperf3_cmd_template = 'iperf3 -c %s %s -p %d -J -Z -l 1M'
    iperf3_config = (config.server, mstr, config.iperf_baseport + offset)
    iperf3_cmd = iperf3_cmd_template % iperf3_config 
    print 'iperf cmd:', iperf3_cmd
    proc = exec_cmd(iperf3_cmd, rhost)
    return [proc]

def roce_incast_cmd(config):
    if config.verb == READ_RC:
        #return config.rone_code_dir + '/code/roce_read_incast_write0'
        return config.rone_code_dir + '/code/roce_read_incast'
    elif config.verb == WRITE_UC:
        return config.rone_code_dir + '/code/roce_write_incast_write0'
    else:
        return None

def start_roce_incast_clients(config):
    msgsize = config.msg_size
    incast_loc = roce_incast_cmd(config)
    incast_servers = ''.join(['%s,' % client for client in config.clients])
    numsegs = numsegs_for_msgsize(config)
    window_in_segs = config.window_size / config.seg_size
    if config.verb == READ_RC:
        cmd = '%s -p %d -b %d -h %s -e 1 -c 1 -n %d -m %d -q %d -M %d' % (incast_loc,
            config.rone_baseport, config.rone_ibaseport, incast_servers, numsegs,
            config.seg_size, window_in_segs, len(config.clients))
    elif config.verb == WRITE_UC:
        cmd = '%s -p %d -b %d -h %s -e 1 -c 1 -q %d -M %d' % (incast_loc,
            config.rone_baseport, config.rone_ibaseport, incast_servers,
            window_in_segs, len(config.clients))
    print 'incast cmd:', cmd
    if hasattr(config, 'timeout'):
        timeout = config.timeout
    else:
        timeout = None
    print 'timeout:', timeout
    proc = exec_cmd(cmd, config.server_ssh, timeout=timeout)

    if config.verb == WRITE_UC:
        num_pings = 500
        ping_procs = start_ping_clients(config, num_pings)
        return {'incasts': [proc], 'pings': ping_procs}
    else:
        return [proc]

def rone_incast_cmd(config):
    if config.verb == READ_RC:
        return config.rone_code_dir + '/code/rone_read_incast'
    elif config.verb == WRITE_UC:
        return config.rone_code_dir + '/code/rone_write_incast_write0'
    else:
        return None

def start_rone_incast_clients(config):
    msgsize = config.msg_size
    print 'msgsize:', msgsize
    incast_loc = rone_incast_cmd(config)
    incast_servers = ''.join(['%s,' % client for client in config.clients])
    numsegs = numsegs_for_msgsize(config)
    if hasattr(config, 'ratelimit') and not config.ratelimit:
        ratelimit_str = '-R 0 '
    else:
        ratelimit_str = ''
    if config.verb == READ_RC:
        cmd = '%s -p %d -b %d -h %s -e 1 -c 1 %s -n %d -m %d -M %d' % (incast_loc,
            config.rone_baseport, config.rone_ibaseport, incast_servers, ratelimit_str,
            numsegs, config.seg_size, len(config.clients))
    elif config.verb == WRITE_UC:
        cmd = '%s -p %d -b %d -h %s -e 1 -c 1 %s -M %d' % (incast_loc,
            config.rone_baseport, config.rone_ibaseport, incast_servers,
            ratelimit_str, len(config.clients))
    print 'incast cmd:', cmd
    if hasattr(config, 'timeout'):
        timeout = config.timeout
    else:
        timeout = None
    print 'timeout:', timeout
    proc = exec_cmd(cmd, config.server_ssh, timeout=timeout)
    if config.verb == WRITE_UC:
        return {'incasts': [proc]}
    else:
        return [proc]

def start_ping_clients(config, num_pings):
    # TODO: This should try to guess how long to run for.
    PING_COMMAND_TEMPLATE = 'sudo ping -i %(ival)s -c %(num)s %(dst)s'
    ping_ival = 0.005
    ping_config = {'ival': ping_ival, 'num': num_pings}
    procs = []
    for client in config.clients:
        pc = ping_config.copy()
        pc['dst'] = client
        ping_cmd = PING_COMMAND_TEMPLATE % pc
        proc = exec_cmd(ping_cmd, config.server_ssh)
        procs.append(proc)
    return procs

def start_incast_clients(config):
    if hasattr(config, 'msg_size'):
        msgsize = config.msg_size
    else:
        msgsize = numsegs_for_runlen(config) * config.seg_size
    incast_loc = config.rone_code_dir + '/bin/incast/incast_client'
    incast_servers = ' '.join(['%s %d' % (client, config.iperf_baseport) \
                               for client in config.clients])
    print 'incast_servers:', incast_servers
    cmd = '%s %d %s' % (incast_loc, msgsize, incast_servers)
    print 'incast cmd:', cmd
    proc = exec_cmd(cmd, config.server_ssh)
    num_pings = 150
    ping_procs = start_ping_clients(config, num_pings)
    return {'incasts': [proc], 'pings': ping_procs}

def process_roce_clients_output(config, clients):
    print 'RoCE Clients:'
    client_gbps = []
    for client in clients:
        out = get_proc_output(client).read()
        err = get_proc_err(client).read()
        # DEBUG
        print 'Client output:', out
        print 'Client err:', err

        outlines = out.split('\n')
        values = outlines[-3].split()

        # Error checking
        seg_size = int(values[0])
        if seg_size != config.seg_size:
            raise ValueError('Unexpected client segment size!')

        gbps = float(values[3])
        client_gbps.append(gbps)

    agg_tput_results = {'50p': get_percentile(client_gbps, 50),
                        'avg': 1.0 * sum(client_gbps) / len(client_gbps),
                        'unfairness': max(client_gbps) - min(client_gbps),
                        'clients': client_gbps,
                        #XXX: Looking at this aggregate throughput is
                        # misleading because it can be greater than 10Gbps.
                        #'agg': sum(client_gbps),
    }
    return agg_tput_results

def process_rone_clients_output(config, clients):
    print 'RoNE Clients:'
    client_gbps = []
    for client in clients:
        client.kill()
        out = client.stdout.read()
        # DEBUG
        print out

        outlines = out.split('\n')
        values = outlines[-2].split()

        # Error checking
        if values[0] != 'throughput':
            raise ValueError('Unexpected RoNE client output!')

        gbps = float(values[-2])
        client_gbps.append(gbps)

    agg_tput_results = {'avg': sum(client_gbps)}
    return agg_tput_results

def process_iperf3_agg_tput(client_json_objs):
    client_tputs = []
    for json_obj in client_json_objs:
        client_gbps = float(json_obj["end"]["sum_sent"]["bits_per_second"])/1e9
        client_tputs.append(client_gbps)
    
    #print client_tputs
    agg_tput_results = {'50p': get_percentile(client_tputs, 50),
                        'avg': 1.0 * sum(client_tputs) / len(client_tputs),
                        'unfairness': max(client_tputs) - min(client_tputs),
                        'clients': client_tputs,
                        #XXX: Looking at this aggregate throughput is
                        # misleading because it can be greater than 10Gbps.
                        #'agg': sum(client_tputs),
    }
    return agg_tput_results

def process_iperf3_clients_output(config, clients):
    client_json_objs = []
    for proc in clients:
        out = get_proc_output(proc)
        try:
            json_obj = json.load(out)
        except:
            print 'Error. out:', out.read()
            print 'stderr:', proc[2].read()
            raise
        client_json_objs.append(json_obj)
    agg_tput_results = process_iperf3_agg_tput(client_json_objs)
    #flow_tput_results = process_flow_tput(client_json_objs)
    return agg_tput_results

def process_roce_incast_clients_output(config, clients):
    if config.verb == WRITE_UC:
        servers = clients['servers']
        incast_clients = clients['incasts']
        ping_clients = clients['pings']

        #try:
        #    res = process_rone_incast_clients_output_base(config, incast_clients)
        #except (yaml.parser.ParserError, yaml.scanner.ScannerError) as e:
        #    res = None
        res = None

        pinglatencies = process_ping_output(config, ping_clients)

        clientlatencies = []
        for client in incast_clients:
            out = get_proc_output(client).read()
            stderr = client[2]
            print 'client stderr:', stderr.read()
            print 'client out:', out
            for line in out.splitlines():
                match = re.match(r"- \[.*,.*\]", line)
                if match:
                    try:
                        lat = yaml.load(line)[0][1]
                        clientlatencies.append(lat)
                    except:
                        pass

        if res == None:
            res = {'tput': None, 'latency': None}

        server_tputs = []
        for server in servers:
            out = get_proc_output(server).read()
            print 'server out:', out
            for line in out.splitlines():
                match = re.match(r"- \[.*", line)
                if match:
                    gbps = yaml.load(line)[0][3]
                    server_tputs.append(gbps)
        res['tput'] = {'clients': server_tputs}

        #res['latency'] = server_latencies
        res['latency'] = clientlatencies
        res['pinglatency'] = pinglatencies
        print 'res:', yaml.dump(res)
        return res
    else:
        return process_rone_incast_clients_output_base(config, clients)

def process_rone_incast_clients_output(config, clients):
    # Write UC needs to get the data from the servers
    if config.verb == WRITE_UC:
        servers = clients['servers']
        incast_clients = clients['incasts']

        client_gbps = []
        latencies = []
        for server in servers:
            print 'server:'
            out = get_proc_output(server).read()
            #print out

            yaml_obj = yaml.load(out)
            print yaml.dump(yaml_obj)

            # TPUT
            tput = yaml_obj['tput']
            assert(len(tput) == 1)
            assert(tput[0][0] == 'WRITE_UC')
            qptype, totTime, totBytes, gbps, numSockets = tput[0]
            client_gbps.append(gbps)

            # Latency
            yaml_latency = yaml_obj['latency']
            yaml_latency = [x[1] for x in yaml_latency]
            latencies.extend(yaml_latency)
        agg_tput_results = {'incast_gbps': [],
                            'clients': client_gbps,
        }
        return {'tput': agg_tput_results, 'latency': latencies}
    else:
        return process_rone_incast_clients_output_base(config, clients)


def process_rone_incast_clients_output_base(config, clients):
    print 'RoNE incast Clients:'
    client_gbps = []
    incast_gbps = []
    for client in clients:
        stderr = client[2]
        try:
            print 'stderr:', stderr.read()
            out = get_proc_output(client).read()
        except socket.timeout:
            return None
        # DEBUG
        print 'out:', out

        yaml_obj = yaml.load(out)
        yaml_tput = yaml_obj['tput']
        #XXX: The client crashed and just output latency
        if len(yaml_tput[-1]) == 2:
            continue


        if config.verb == WRITE_UC:
            for qptype, totTime, totBytes, gbps, numSockets in yaml_tput[0:-1]:
                if qptype == 'WRITE_UC':
                    client_gbps.append(gbps)
        else:
            # The last is aggregate.  TODO: Also look at aggregate throughput
            for totTime, totBytes, gbps, numSockets in yaml_tput[0:-1]:
                client_gbps.append(gbps)
            totTime, totBytes, gbps, numSockets = yaml_tput[-1]
            incast_gbps.append(gbps)

        yaml_latency = yaml_obj['latency']
        latencies = [x[1] for x in yaml_latency]

    print 'client_gbps:', yaml.dump(client_gbps)
    print 'incast_gbps:', yaml.dump(incast_gbps)

    if len(client_gbps) == 0 and len(incast_gbps) == 0:
        return None

    agg_tput_results = {'50p': get_percentile(client_gbps, 50),
                        'avg': 1.0 * sum(client_gbps) / len(client_gbps),
                        'unfairness': max(client_gbps) - min(client_gbps),
                        'incast_gbps': incast_gbps,
                        'clients': client_gbps,
                        #XXX: Looking at this aggregate throughput is
                        # misleading because it can be greater than 10Gbps.
                        #'agg': sum(client_gbps),
    }

    return {'tput': agg_tput_results, 'latency': latencies}

def process_ping_output(config, clients):
    latencies = []
    for client in clients:
        out = get_proc_output(client).read()
        prev_icmp_seq = 0
        for line in out.splitlines():
            #print line

            match = re.match(r".*icmp_seq=(\d+) .*", line)
            if match:
                icmp_seq = int(match.groups()[0])
                #print 'icmp_seq:', icmp_seq, 'prev:', prev_icmp_seq
                if prev_icmp_seq < icmp_seq - 1:
                    missed = [1e10] * (icmp_seq - prev_icmp_seq + 1)
                    latencies.extend(missed)
                prev_icmp_seq = icmp_seq

            match = re.match(r".*time=(%s) ms" % FLOAT_DESC_STR, line)
            if match:
                l = float(match.groups()[0]) * 1000
                latencies.append(l)
    return latencies

def process_incast_clients_output(config, clients):
    incast_clients = clients['incasts']
    ping_clients = clients['pings']
    client_gbps = []
    incast_gbps = []
    for client in incast_clients:
        out = get_proc_output(client).read()
        # DEBUG
        print out

        yaml_obj = yaml.load(out)
        # The first item is documenation.  The last is aggregate.
        # TODO: Also look at aggregate throughput
        for totTime, totBytes, gbps, numSockets in yaml_obj[1:-1]:
            client_gbps.append(gbps)
        totTime, totBytes, gbps, numSockets = yaml_obj[-1]
        incast_gbps.append(gbps)

    print 'client_gbps:', yaml.dump(client_gbps)
    print 'incast_gbps:', yaml.dump(incast_gbps)

    agg_tput_results = {'50p': get_percentile(client_gbps, 50),
                        'avg': 1.0 * sum(client_gbps) / len(client_gbps),
                        'unfairness': max(client_gbps) - min(client_gbps),
                        'incast_gbps': incast_gbps,
                        'clients': client_gbps,
                        #XXX: Looking at this aggregate throughput is
                        # misleading because it can be greater than 10Gbps.
                        #'agg': sum(client_gbps),
    }

    latencies = process_ping_output(config, ping_clients)

    return {'tput': agg_tput_results, 'latency': latencies}

#
# XXX: I realize classes were created to fix the below code.  Or function
# pointers.  But this is python, so classes.  This should be fixed.
#
# But honestly, the code isn't that different and it hardly matters because
# Python is not statically typed.  I wish python was statically typed.
#

def start_framework_servers(config, numservers):
    if config.framework not in TRANSPORTS:
        raise ValueError('Unexpected framework: \'%s\'' % config.framework)

    if config.framework == RoNE:
        #servers = start_rone_servers(config, numservers)
        servers = start_rone_incast_servers(config, numservers)
    elif config.framework == iRoCE:
        servers = start_roce_incast_servers(config, numservers)
    elif config.framework == RoCE:
        servers = start_roce_servers(config, numservers)
    elif config.framework == DCTCP:
        #if hasattr(config, 'msg_size') and config.msg_size < 2**32:
        if hasattr(config, 'msg_size'):
            servers = start_incast_servers(config, numservers)
        else:
            servers = start_iperf3_servers(config, numservers)
    else:
        raise ValueError('Unexpected framework: \'%s\'' % config.framework)

    return servers

# TODO: this function could accept a list of (stdin, stdout, stderr) from
# starting for printing
def kill_framework_servers(config):
    if config.framework not in TRANSPORTS:
        raise ValueError('Unexpected framework: \'%s\'' % config.framework)

    if config.framework == RoNE:
        kill_rone_incast_servers(config)
        kill_roce_incast_servers(config)
        #kill_rone_servers(config)
    elif config.framework == iRoCE:
        kill_roce_incast_servers(config)
        kill_rone_incast_servers(config)
    elif config.framework == RoCE:
        kill_roce_servers(config)
    elif config.framework == DCTCP:
        kill_iperf3_servers(config)
        kill_incast_servers(config)
    else:
        raise ValueError('Unexpected framework: \'%s\'' % config.framework)

def start_framework_clients(config):
    if config.framework not in TRANSPORTS:
        raise ValueError('Unexpected framework: \'%s\'' % config.framework)

    #XXX: Workaround for not the best design at first
    #if config.framework == DCTCP and hasattr(config, 'msg_size') and \
    #        config.msg_size < 2**32:
    if config.framework == DCTCP and hasattr(config, 'msg_size'):
        clients = start_incast_clients(config)
    elif config.framework == iRoCE:
        clients = start_roce_incast_clients(config)
    elif config.framework == RoCE and \
            (config.verb == READ_RC or config.verb == READ_UC):
        #XXX: HACK/Work-around.  The congestion and tcp-friendliness experiments
        # assume that clients send data to the servers.  If it is the opposite, there
        # will not be any congestion.  In the case of READs, servers send data to
        # clients, so we have to reverse the meaning of server and clients.
        #XXX: Now that we have a RoCE incast application, we don't need this anymore
        clients = start_roce_clients_read(config)
    elif config.framework == RoNE:
        clients = start_rone_incast_clients(config)
    else:
        clients = []
        for (offset, rhost) in enumerate(config.client_sshs):
            if config.framework == RoNE:
                cprocs = start_rone_clients(config, offset, rhost)
            elif config.framework == RoCE:
                cprocs = start_roce_clients(config, offset, rhost)
            elif config.framework == DCTCP:
                cprocs = start_iperf3_clients(config, offset, rhost)
            else:
                raise ValueError('Unexpected framework: \'%s\'' % config.framework)
            clients.extend(cprocs)

    return clients

def process_framework_clients_output(config, clients):
    if config.framework not in TRANSPORTS:
        raise ValueError('Unexpected framework: \'%s\'' % config.framework)

    if config.framework == RoNE:
        #res = process_rone_clients_output(config, clients)
        res = process_rone_incast_clients_output(config, clients)
    elif config.framework == iRoCE:
        res = process_roce_incast_clients_output(config, clients)
    #elif config.framework == RoCE and \
    #        (config.verb == READ_RC or config.verg == READ_UC):
    #    res = process_roce_clients_output(config, clients)
    elif config.framework == RoCE:
        res = process_roce_clients_output(config, clients)
    elif config.framework == DCTCP:
        #if hasattr(config, 'msg_size') and config.msg_size < 2**32:
        if hasattr(config, 'msg_size'):
            res = process_incast_clients_output(config, clients)
        else:
            res = process_iperf3_clients_output(config, clients)
    else:
        raise ValueError('Unexpected framework: \'%s\'' % config.framework)

    return res

def configure_dcqcn(config):
    print 'Configuring DCQCN...'
    dcqcn_conf_cmd_base = 'sudo ' + config.rone_code_dir + '/conf/config_dcqcn_'
    if config.dcqcn:
        dcqcn_conf_cmd = dcqcn_conf_cmd_base + 'on.sh'
    else:
        dcqcn_conf_cmd = dcqcn_conf_cmd_base + 'off.sh'
    subprocess.check_call(dcqcn_conf_cmd, shell=True)

    rhost_sshs = config.client_sshs[:] + [config.server_ssh]
    for rhost_ssh in rhost_sshs:
        stdin, stdout, stderr = exec_cmd(dcqcn_conf_cmd, rhost_ssh)
        out = stdout.read()
        print out
        if out.find('Failed') >= 0:
            raise

def reset_rate_limiters(config):
    print 'Configuring DCQCN...'
    ratelimiter_conf_cmd = 'sudo ' + config.rone_code_dir + '/conf/config_ratelimit_reset.sh'
    subprocess.check_call(ratelimiter_conf_cmd, shell=True)

    rhost_sshs = config.client_sshs[:] + [config.server_ssh]
    for rhost_ssh in rhost_sshs:
        stdin, stdout, stderr = exec_cmd(ratelimiter_conf_cmd, rhost_ssh)
        out = stdout.read()
        #print out

def configure_cluster(config):
    # Configure DCQCN
    configure_dcqcn(config)

    # Reset rate-limiters
    reset_rate_limiters(config)

    # Do nothing else for now
    pass
