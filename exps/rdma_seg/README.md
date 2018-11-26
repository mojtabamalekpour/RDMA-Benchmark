# Experiment to measure the impact of RDMA verb sizes on CPU utilization

## Notable files:

- `gen_rdma_seg_conf.py`: Generate experiment configuration files.
- `run_rdma_seg.sh`: Run multiple experiments.
- `./gen_rdma_seg_lines.py`: Parse and aggregate results into lines for
  a figure.
- `./convert_rdma_sig_lines.py`: Convert from "signals per verb" lines
  to "bytes per signal" lines.
- `./plot_rdma_seg_lines.py`: Plot a YAML file of lines for the figure.

## Running an experiment:

Use the following steps to generate experiment configuration files, run the
experiment, parse the results, and then plot the data:

1. Make the `results` and `conf` directories.
- ```mkdir results conf```

2. Generate configuration files.
- ```./gen_rdma_seg_conf.py```

3. Run the experiments.
- ```tmux new -s exps; ./run_rdma_seg.sh```
- Note: the program `tmux` is very helpful for running experiments
  without requiring an open ssh session.  See the [following
  guide](https://www.hamvocke.com/blog/a-quick-and-easy-guide-to-tmux/)
  for more information.
- Note: For reasons unknown to me, the `ib_read_bw` benchmark program
  may fail.  If this happens, you should be able to continue trying to
  rerun `./run_rdma_seg.sh`.  It should skip experiments that you've
  already run and start over from the failed experiment.

4. Parse the results and generate the lines for the figures.
- ```./gen_rdma_seg_lines.py```
- ```./convert_rdma_sig_lines.py --pltdata rdma_seg_cpu.segsize.lines.yaml```

5. Plot the results.
- ```./plot_rdma_seg_lines.py --pltdata rdma_seg_cpu.segsize.lines.yaml```
- ```./plot_rdma_seg_lines.py --pltdata rdma_seg_cpu.B_per_sig.lines.yaml```
- **NOTE: Your results will not match the results in the RoGUE paper
  because you are using entirely different CPUs (ARM64 vs. x86)!**
