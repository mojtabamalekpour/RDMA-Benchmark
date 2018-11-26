#/bin/bash
TIME=10000000
name=`ls log*`

for filename in ./*.txt; do
	thro=`cat $filename | grep Throughput | cut -d " " -f3`
	echo $thro >> throghput.dat
	
	delay=`cat $filename | grep delay | cut -d " " -f5`
	echo $delay>> delay.dat

	cpu=`cat $filename | grep CPU | cut -d " " -f7`
	echo $cpu >> cpu.dat
done
