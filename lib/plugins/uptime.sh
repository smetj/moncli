#!/bin/bash

echo "seconds:$(cat /proc/uptime |cut -f '1' -d ' ')"
echo "~==.==~"
uptime
