# Vanilla RDMA Performance Experiment

## Figures:
First figure shows the effect of verb size on the cpu utilization. In this graph, the larger the segment is, the more cpu utilization is achieved.
In second graph, at all of scenarios, the CPU utilization decreases when the size increase, because less overhead is required to do basic operation e.g. mem alloc and other cpu bounded operations. Moreover, when the number of signal increases performance is better.

## Discussion:
I would say the reason is mostly because the CPU is different from the paper and then the results are also different.

# Custom RDMA Program Performance Experiment
## Design:

In order to make a RDMA client server, I used the following code:

https://github.com/pixelrazor/rdma-cs/tree/master/rdma%20v1

Here are what the code is doing (thegeekinthecorner):
- Server starts listening for connections.
- Client posts a receive operation for a flow-control message and initiates a connection to the server.
- Server posts a receive operation for an RDMA write with immediate data and accepts the connection from the client.
- Server sends the client its target memory region details.
- Client re-posts a receive operation then responds by writing the name of the file to the server’s memory region. The immediate data field contains the length of the file name.
- Server opens a file descriptor, re-posts a receive operation, then responds with a message indicating it is ready to receive data.
- Client re-posts a receive operation, reads a chunk from the input file, then writes the chunk to the server’s memory region. The immediate data field contains the size of the chunk in bytes.
- Server writes the chunk to disk, re-posts a receive operation, then responds with a message indicating it is ready to receive data.
- Repeat steps 7, 8 until there is no data left to send.
- Client re-posts a receive operation, then initiates a zero-byte write to the server’s memory. The immediate data field is set to zero.
- Server responds with a message indicating it is done.
- Client closes the connection.
- Server closes the file descriptor.

And I just add the arguments and I also made the code to be executing for "lifetime" amount of time.

## Description
To run code, start server as

```./server 5000```

then start the client

```./client <address> <port> <duration(ms)> <verbType(READ/WRITE)> <memorySizetoRegister(Byte)> <logFileAdd> ```

Here is an example

```./client 10.10.1.1 5000 10000000 READ 512 log512.txt```

## Note:
- Verbs should be either WRITE or READ.
- make sure name files as follow:
-- log064 or log512 and et.

Now you can execute plot.sh

```./plot.sh```

This command will create three files contains the digest of the numbers from experiment.

In order to plot the graph as pdf, just execute:

```python plot.py```

and there will be three pdf files.

## Figures:
In all figures, y axes is the size of the registered memory and the x:
- In throughput, its the throughput Gb/s
- In delay its microseconds that shows the average delay for all ping-pong at the simulation runtime (hope this is what you wanted!!!)
- In cpu, its the percent of the average cpu utilization

## Discussion:
The effect on registered memory is:
-- throughput, the lower the better!
-- delay, same as we expected. RTT doesn't change upon changing the register size
-- cpu, larger registered memory cause larger cpu utilization.


## Results:

<embed src="http://yoursite.com/the.pdf">
        <p>To see the thrughput graph, click here: <a href="https://github.com/uic-data-center-systems/hw2-mojtabamalekpour/blob/master/code/rdmav1/throughput.pdf">Throughput</a>.</p>
</embed>


<embed src="http://yoursite.com/the.pdf">
        <p>To see the cpu utilazation graph, click here: <a href="https://github.com/uic-data-center-systems/hw2-mojtabamalekpour/blob/master/code/rdmav1/cpu.pdf">Utilazation</a>.</p>
</embed>

<embed src="http://yoursite.com/the.pdf">
        <p>To see the delay graph, click here: <a href="https://github.com/uic-data-center-systems/hw2-mojtabamalekpour/blob/master/code/rdmav1/delay.pdf">Delay</a>.</p>
</embed>


