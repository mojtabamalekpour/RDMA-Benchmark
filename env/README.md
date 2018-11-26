# Environment Configuration for RDMA communication.

Most notably, building an RDMA application requries installing OFED.  Also, it
is important to install ansible and setup passwordless SSH.


## Notable files:

- `bootstrap_env.sh`: Pre-ansible bootstrap file to run on each machine.
- `packages.yml`: An ansible script to install packages via apt and install OFED
- `cluster-hosts`: A file that contains the IPs of the servers in the cluster

## Install guide:

### Pre-ansible

First ansible must be installed:

1. Generate some keys for the cluster to get ssh to work. (Note: this probably
isn't the best thing to do and you can skip this step if you already have
passwordless ssh between the machines configured.)
```
mkdir keys
ssh-keygen -f keys/id_rsa
```

2.  On each server, copy the keys and setup env variables. (Use parallel ssh if
there are many servers)
```
./bootstrap_env.sh
```

### Ansible

1.  Test with:
```
ansible all -i cluster-hosts -m ping
```

2. Run the following command and verify that it completes correctly:
```
ansible-playbook -i cluster-hosts packages.yml
```

3.  Installing OFED and configuring NIC firmware packet pacing both ask for
rebooting the server.  After this, on every server `reboot` after running
ansible for the first time.
    - Note: You will have to rerun `bootstrap_env.sh` on every machine (with
      ansible) every time you reboot the machine.

### Verification

To verify that the installation worked correctly, use a program from the perftest suite like `ib_read_bw`, `ib_write_bw`, `ib_send_bw`, or `ib_read_lat`.

For example, to use `ib_read_bw` to verify connectivity:

1. Run the following on node-1:
```
sudo ib_read_bw -d mlx4_0 -i 2 -D 10 -c RC --report_gbits
```

2. Run the following on node-0:
```
sudo ib_read_bw -d mlx4_0 -i 2 -D 10 -c RC --report_gbits 10.10.1.1
```

These commands should exist, and this should succeed and tell you that
it was able to send at line-rate (>9Gbps).

**NOTE**: The `-i 2` command *must* be included when you are using CloudLab
Utah!  Both of the ports of the NIC support RDMA, but the first port is for use
in the control network only!  The `-i 2` flag should force RDMA to use the
second port that is connected to the experimental network.  Note that you will
need to manually select the correct GID in your own code!

Finally, to verify that you are using the correct, you should look at
Infiniband counters for both port 1 and port 2 with the following
commands:
```
tail /sys/class/infiniband/mlx4_0/ports/1/counters/port*packets
tail /sys/class/infiniband/mlx4_0/ports/2/counters/port*packets
```
When you run any RDMA program, you should observe the counters for port *2*
increasing while the counters for port *1* stay the same.
