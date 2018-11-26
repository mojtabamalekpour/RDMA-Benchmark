import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt


y=[512, 256,128,64]
with open('throghput.dat') as f:
    lines = f.readlines()
    x = [line.split()[0] for line in lines]
ff = plt.figure()
plt.plot(y,x, "-")
plt.show()
ff.savefig("throughput.pdf", bbox_inches='tight')

with open('cpu.dat') as f1:
    lines1 = f1.readlines()
    x1 = [line.split()[0] for line in lines1]
ff1= plt.figure()
plt.plot(y,x1, "-")
plt.show()
ff1.savefig("cpu.pdf", bbox_inches='tight')


with open('delay.dat') as f3:
    lines3 = f3.readlines()
    x3 = [line.split()[0] for line in lines3]
ff3= plt.figure()
plt.plot(y,x3, "-")
plt.show()
ff3.savefig("delay.pdf", bbox_inches='tight')
