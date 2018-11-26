#!/usr/bin/python

import argparse
import os
import sys
import yaml

SIGB = ['16KB', '64KB', '256KB']

def get_num_sig_from_lname(lname):
    s = lname.split('.')[-1]
    s = s[:s.find('S')]
    return int(s)

def get_seg_size_str(seg_size):
    if seg_size < 2**20:
        return '%dKB' % (seg_size / 1024)
    else:
        return '%dMB' % (seg_size / 1024 / 1024)

def convert_pltdata(pltdata):
    new_lines = {}

    for line in pltdata['lines']:
        xs = line['xs']
        ys = line['ys']
        num_sig = get_num_sig_from_lname(line['lname']) 

        for (x, y) in zip(xs, ys):
            #XXX: for signalsize lines
            #signal_size = x
            #verb_size = x / num_sig

            #XXX: for segsize lines
            verb_size = x
            signal_size = verb_size * num_sig

            if get_seg_size_str(signal_size) in SIGB:
                if signal_size not in new_lines:
                    new_line = {'lname': get_seg_size_str(signal_size),
                        'x2y': {}
                    }
                    new_lines[signal_size] = new_line
                new_lines[signal_size]['x2y'][verb_size] = y


    for nl in new_lines.values():
        xs = nl['x2y'].keys()
        xs.sort()
        nl['xs'] = xs
        ys = [nl['x2y'][x] for x in xs]
        nl['ys'] = ys
        del nl['x2y']

    pltdata = {'lines': new_lines.values(), 'xlabel': 'Verb Size (B)'}

    return pltdata


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Convert line formats')
    parser.add_argument('--pltdata', help='Data files containing the lines '
        'and other plot metadata', required=True)
    args = parser.parse_args()

    user_pltdata = None
    with open(args.pltdata) as pltdataf:
        user_pltdata = yaml.load(pltdataf)

    pltdata = convert_pltdata(user_pltdata)


    spoutfname = args.pltdata.split('.')
    spoutfname[-3] = 'B_per_sig'
    outfname = '.'.join(spoutfname)
    spoutfname[-1] = 'pdf'
    pdffname = '.'.join(spoutfname)
    pltdata['outf'] = pdffname
    with open(outfname, 'w') as outf:
        yaml.dump(pltdata, outf)

    print yaml.dump(pltdata)
    #print yaml.dump(new_lines.values())

if __name__ == '__main__':
    main()
