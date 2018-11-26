#!/usr/bin/python

import argparse
import os
import sys
import yaml

sys.path.insert(0, os.path.abspath('..'))
from rone_plt_common import *

# Default config
CPU_PLT_CONFIG_DEFAULTS = {
    # Experiment naming config
    'expname': None,
    'outf': None,
    'lines': None,

    # Labels
    'title': 'RDMA Segmentation Overhead',
    'xlabel': 'Segment size (KB)',
    'ylabel': 'Percent CPU Utilization\n(Sum of per-core utilization)',

    # Matplotlib config
    'xticks': None,
    'ymin': None,
    'ymax': None,
    'legend_width': 2,
}


class CpuUtilLineData(object):
    def __init__(self, *initial_data, **kwargs):
        for dictionary in initial_data:
            for key in dictionary:
                setattr(self, key, dictionary[key])
        for key in kwargs:
            setattr(self, key, kwargs[key])

class CpuUtilPltConfig(object):
    def __init__(self, *initial_data, **kwargs):
        for key in CPU_PLT_CONFIG_DEFAULTS:
            setattr(self, key, CPU_PLT_CONFIG_DEFAULTS[key])
        for dictionary in initial_data:
            for key in dictionary:
                if not hasattr(self, key):
                    print 'WARNING! Unexpected attr: %s' % key
                setattr(self, key, dictionary[key])
        for key in kwargs:
            if not hasattr(self, key):
                print 'WARNING! Unexpected attr: %s' % key
            setattr(self, key, kwargs[key])

        # Parse the lines as well
        if hasattr(self, 'lines'):
            print 'lines:', self.lines
            self.lines = [CpuUtilLineData(line) for line in self.lines]

def get_seg_size_str(seg_size):
    if seg_size < 2**20:
        return '%dKB' % (seg_size / 1024)
    else:
        return '%dMB' % (seg_size / 1024 / 1024)

def get_xticks_from_line(line):
    return [get_seg_size_str(seg_size) for seg_size in line.xs]

def get_xticks_and_update_xs(pltdata):
    # Get the xticks
    xs_set = set()
    for line in pltdata.lines:
        xs_set.update(line.xs)
    xs = list(xs_set)
    xs.sort()
    x2idx = dict(zip(xs, range(len(xs))))
    xticks = [get_seg_size_str(seg_size) for seg_size in xs]

    print 'xs_set:', xs_set
    print 'xticks:', yaml.dump(xticks)
    print 'x2idx:', x2idx

    # Update the lines xs
    for line in pltdata.lines:
        line.xs = [x2idx[x] for x in line.xs]

    return xticks

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Measure the CPU utilization '
        'of the Linux TCP stack (DCTCP)')
    parser.add_argument('--pltdata', help='Data files containing the lines '
        'and other plot metadata', required=True, type=argparse.FileType('r'))
    args = parser.parse_args()

    user_pltdata = yaml.load(args.pltdata)

    pltdata = CpuUtilPltConfig(user_pltdata)
    
    # Update the xticks
    if pltdata.xticks == None:
        pltdata.xticks = get_xticks_and_update_xs(pltdata)

    print 'xticks:', pltdata.xticks

    plot_line_data(pltdata)

    # Show the figure
    show()

if __name__ == '__main__':
    main()
