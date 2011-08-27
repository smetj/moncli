#!/usr/bin/python
import sys

sys.path.append('/opt/moncli/lib/monitoring')
from event import SystemRequest

request=SystemRequest()
request.reason='Just doing some testing'
request.cycle='0'
request.subject='Moncli status'
request.target='Sandbox'
request.destination={"type":"file","locations":['/tmp/system_request.txt']}
request.addCommand({'scheduler':'reset'})



try:
	request.integrity()
except Exception as err:
	print "Problem with: %s"%(err)
else:
	print request.construct(style='json')

