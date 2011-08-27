#!/bin/bash

load=$(cat /proc/loadavg)
echo "1_min:$(echo $load|cut -d " " -f 1)"
echo "5_min:$(echo $load|cut -d " " -f 2)"
echo "15_min:$(echo $load|cut -d " " -f 3)"
echo "~==.==~"
top -b -n 1


