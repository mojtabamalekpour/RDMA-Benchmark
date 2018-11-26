#!/usr/bin/python

import argparse
import os
import sys
import yaml

from gen_rdma_seg_conf import *

# Use our own parameters for debugging
FRAMEWORKS = [RoCE]

# 
AVG, MED = 'avg', 'med'
PMETRIC = MED

def get_avg_results(framework, verb, seg_size, signal_ifreq):
    cpu_results = []
    for run in RUNS:
        config = get_rdma_seg_config(framework, verb, seg_size,
            signal_ifreq, run)
        outfname = config['outf']
        if not os.path.exists(outfname):
            print 'Missing output file: \'%s\'' % outfname
        else:
            with open(outfname) as outf:
                run_result = yaml.load(outf)
                if PMETRIC == AVG:
                    cpu_results.append(run_result['client_cpu']['avg'])
                elif PMETRIC == MED:
                    cpu_results.append(run_result['client_cpu']['50p'])
    return cpu_results

def gen_by_segsize():
    lines = []
    for framework in [RoCE]:
        for verb in VERBS:
            for signal_ifreq in SIGNAL_IFREQ:
                line_name = '%s.%s.%dSig' % (framework, verb, signal_ifreq)
                xs, ys = [], []
                for seg_size in SEG_SIZES:
                    cpu_results = get_avg_results(framework, verb, seg_size,
                        signal_ifreq)

                    xs.append(seg_size)
                    if len(cpu_results) > 0:
                        avg_cpu = 1.0 * sum(cpu_results) / len(cpu_results)
                        ys.append(avg_cpu)
                    else:
                        ys.append(None)

                line_data = {'lname': line_name, 'xs': xs, 'ys': ys}
                lines.append(line_data)


    # Generate the plot config
    config = get_rdma_seg_config(framework, verb, seg_size,
        signal_ifreq, 0)
    plot_data = {
        'outf': 'plots.%s.segsize.pdf' % config['expname'],
        'lines': lines,
        'xlabel': 'Segment size (KB)',
    }

    #TODO: Allow the lines file to be configured?
    print yaml.dump(plot_data)
    outfname = '%s.segsize.lines.yaml' % config['expname']
    with open(outfname, 'w') as outf:
        yaml.dump(plot_data, outf)

def gen_by_sigsize():
    lines = []
    for framework in [RoCE]:
        for verb in VERBS:
            for signal_ifreq in SIGNAL_IFREQ:
                line_name = '%s.%s.%dSig' % (framework, verb, signal_ifreq)
                xs, ys = [], []
                signal_sizes = [s for s in SEG_SIZES if (s/signal_ifreq >= 1024)]
                print line_name, 'signal_sizes:', yaml.dump(signal_sizes)
                for signal_size in signal_sizes:
                    seg_size = signal_size / signal_ifreq
                    cpu_results = get_avg_results(framework, verb, seg_size,
                        signal_ifreq)

                    xs.append(signal_size)
                    if len(cpu_results) > 0:
                        avg_cpu = 1.0 * sum(cpu_results) / len(cpu_results)
                        ys.append(avg_cpu)
                    else:
                        ys.append(None)

                line_data = {'lname': line_name, 'xs': xs, 'ys': ys}
                lines.append(line_data)

    # Generate the plot config
    config = get_rdma_seg_config(framework, verb, seg_size,
        signal_ifreq, 0)
    plot_data = {
        'outf': 'plots.%s.signalsize.pdf' % config['expname'],
        'lines': lines,
        'xlabel': 'Size of Signalled Data (KB)',
    }

    #TODO: Allow the lines file to be configured?
    print yaml.dump(plot_data)
    outfname = '%s.signalsize.lines.yaml' % config['expname']
    with open(outfname, 'w') as outf:
        yaml.dump(plot_data, outf)

def main():
    gen_by_segsize()

    #gen_by_sigsize()

if __name__ == '__main__':
    main()
