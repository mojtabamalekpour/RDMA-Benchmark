#!/usr/bin/python
import matplotlib
matplotlib.use('Agg')


import itertools
from pylab import *
import matplotlib.cm as mplcm
import matplotlib.colors as mplcolors

params = {#'text.usetex': True,
    'font.size' : 18,
    #'title.fontsize' : 14,
    'axes.labelsize': 20,
    'text.fontsize' : 20,
    'xtick.labelsize' : 20,
    'ytick.labelsize' : 20,
    #'legend.fontsize' : 'medium',
    'legend.fontsize' : '18',
    'lines.linewidth' : 6,
    'lines.markersize' : 6,
}
rcParams.update(params)

master_linestyles = ['-', '--', '-.', ':']
master_markers = ['o', 'D', 'v', '^', '<', '>', 's', 'p', '*', '+', 'x']
master_hatch = ['+', 'x', '\\', 'o', 'O', '.', '-',  '*']

def plot_line_data(plot_data):
    if not hasattr(plot_data, 'bottom'):
        plot_data.bottom = 0.35
    if not hasattr(plot_data, 'legend_y'):
        plot_data.legend_y = -0.6

    # Setup the figure
    f = figure(figsize=(8, 5))
    f.subplots_adjust(hspace=0.25, wspace=0.185, left=0.20, bottom=plot_data.bottom)
    legend_bbox = (0.45, plot_data.legend_y)
    legend_width = plot_data.legend_width

    # Build the colormap
    color_map = get_cmap('Set1')
    #c_norm = mplcolors.Normalize(vmin=0, vmax=len(plot_data.lines)*2)
    #color_map = get_cmap('gist_stern')
    #color_map = get_cmap('Dark2')
    #color_map = get_cmap('gnuplot')
    #color_map = get_cmap('nipy_spectral')
    c_norm = mplcolors.Normalize(vmin=0, vmax=len(plot_data.lines)*1.7)
    scalar_map = mplcm.ScalarMappable(norm=c_norm, cmap=color_map)
    linescycle = itertools.cycle(master_linestyles)
    markercycle = itertools.cycle(master_markers)

    ax = gca()
    ax.set_color_cycle([scalar_map.to_rgba(i) for i in \
        xrange(len(plot_data.lines))])

    # Plot the data
    for line in plot_data.lines:
        plot(line.xs, line.ys, label=line.lname, linestyle=linescycle.next(),
             marker=markercycle.next())

    # Mess with axes
    yax = ax.get_yaxis()
    yax.grid(True)
    ax.set_xlabel(plot_data.xlabel)
    #ax.set_xlim(xmin=0)
    ax.set_ylabel(plot_data.ylabel)

    # Change xticks:
    if plot_data.xticks:
        print 'xticks!', tuple(plot_data.xticks)
        _ret = xticks(np.arange(len(plot_data.xticks)), tuple(plot_data.xticks))
        #f.autofmt_xdate()
        print _ret

    # Change limits
    if plot_data.ymin != None:
        ylim(ymin = plot_data.ymin)
    if plot_data.ymax != None:
        ylim(ymax = plot_data.ymax)

    #title(get_title(outfname))
    title(plot_data.title, fontsize=12)

    # Add legend
    ax.legend(loc='lower center', bbox_to_anchor=legend_bbox, ncol=legend_width, columnspacing=0.5, handletextpad=0.25, fancybox=True, shadow=True)

    # Save the figure
    print plot_data.outf
    savefig(plot_data.outf)

def plot_bar_data(plot_data):
    num_bars = len(plot_data.bars)
    #data_len = len(plot_data.bars[0].xs)
    data_len = 1

    newparams = {#'text.usetex': True,
        'legend.fontsize' : '16',
    }
    rcParams.update(newparams)

    # Plot config data
    ind = np.arange(data_len)
    width = 0.3

    # Create the figure
    f = figure(figsize=(6,4))
    f.subplots_adjust(hspace=0.25, wspace=0.185, left=0.20, bottom=0.4)
    legend_bbox = (0.45, -0.85)
    legend_width = plot_data.legend_width

    # Build the colormap
    color_map = get_cmap('Set1')
    c_norm = mplcolors.Normalize(vmin=0, vmax=len(plot_data.bars)*1.7)
    scalar_map = mplcm.ScalarMappable(norm=c_norm, cmap=color_map)
    linescycle = itertools.cycle(master_linestyles)
    markercycle = itertools.cycle(master_markers)
    hatchcycle = itertools.cycle(master_hatch)
    ax = gca()
    ax.set_color_cycle([scalar_map.to_rgba(i) for i in \
        xrange(len(plot_data.bars))])

    #print yaml.dump(plot_data.bars)

    # Plot the data
    rects = []
    for bar_i, bar in enumerate(plot_data.bars):
        color = scalar_map.to_rgba(bar_i)
        rect = ax.bar(ind + 0.3 + bar_i * (width + 0.3), [bar.val], width, color=color,
            hatch=hatchcycle.next())
        rects.append(rect)

    # Legend
    ax.legend(rects, [b.bname for b in plot_data.bars], loc='lower center',
        bbox_to_anchor=legend_bbox, ncol=legend_width, columnspacing=0.5,
        handletextpad=0.25, fancybox=True, shadow=True)

    # Mess with axes
    yax = ax.get_yaxis()
    yax.grid(True)
    ax.set_xlabel(plot_data.xlabel)
    #ax.set_xlim(xmin=0)
    ax.set_ylabel(plot_data.ylabel)

    # Change xticks:
    #ax.set_xticks(ind + (width * num_bars / 2.0))
    #ax.set_xticklabels(plot_data.xticks)
    if plot_data.xticks == None:
        tick_params(
            axis='x',          # changes apply to the x-axis
            which='both',      # both major and minor ticks are affected
            bottom='off',      # ticks along the bottom edge are off
            top='off',         # ticks along the top edge are off
            labelbottom='off') # labels along the bottom edge are off
    else:
        ax.set_xticklabels(plot_data.xticks)



    # Change limits
    if plot_data.ymin != None:
        ylim(ymin = plot_data.ymin)
    if plot_data.ymax != None:
        ylim(ymax = plot_data.ymax)

    #title(get_title(outfname))
    #title(plot_data.title, fontsize=12)

    # Save the figure
    print plot_data.outf
    savefig(plot_data.outf)

