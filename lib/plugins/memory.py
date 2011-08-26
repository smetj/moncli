#!/usr/bin/python
import re,os,time
if __name__ == '__main__':
	proc=open('/proc/meminfo')
	for line in proc:
		rule=re.match('(^.*?):\s*(\d*)',line)
		print "%s:%s" %(rule.group(1).lower(),rule.group(2))
	proc.close()
	print "~==.==~"
	print "Values in MB"
	print "".join(os.popen('/usr/bin/free -t -m').readlines())
