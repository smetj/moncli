#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       communication.py
#       
#       Copyright 2010 Jelle Smet <web@smetj.net>
#       
#       This file is part of Monitoring python library.
#       
#           Monitoring python library is free software: you can redistribute it and/or modify
#           it under the terms of the GNU General Public License as published by
#           the Free Software Foundation, either version 3 of the License, or
#           (at your option) any later version.
#       
#           Monitoring python library is distributed in the hope that it will be useful,
#           but WITHOUT ANY WARRANTY; without even the implied warranty of
#           MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#           GNU General Public License for more details.
#       
#           You should have received a copy of the GNU General Public License
#           along with Monitoring python library.  If not, see <http://www.gnu.org/licenses/>.

from time import tzname
from time import time
from platform import node
from uuid import uuid4
import json
import re
class Event():
	''' Wrapper class which holds report & request classes '''
	def __init__ (self):
		""" Class initialiser """
		self.report=Report()
	def loadRequest(self,data):
		'''Loads the data into the requestReport.'''
		if data['type'] == 'reportRequest':
			self.request=ReportRequest()
		elif data['type'] == 'systemRequest':
			self.request=SystemRequest()
		else:
			raise Exception('A request event type can only be "reportRequest" or "systemRequest".')
			
		self.request.integrity(request=data)
		for item in self.request.variables:			
			setattr(self.request,item,data[item])	
	def finalizeReport(self):
		if self.request.type == 'reportRequest':
			self.report.destination = self.request.destination
			self.report.subject = self.request.subject
			self.report.requestFQDN = self.request.FQDN
			self.report.requestUUID = self.request.UUID
			self.report.tags = self.request.tags
			self.report.target = self.request.target
			self.report.cycle = self.request.cycle
			self.report.weight_map = self.request.weight_map
			self.report.format = self.request.format
			self.report.plugin = self.request.plugin
			self.report.pluginHash = self.request.pluginHash
			self.report.pluginTimeout = self.request.pluginTimeout
			self.report.pluginParameters = self.request.pluginParameters
		if self.request.type == 'systemRequest':
			self.report.destination = self.request.destination
			self.report.subject = self.request.subject
			self.report.requestFQDN = self.request.FQDN
			self.report.requestUUID = self.request.UUID
			self.report.tags = self.request.tags
			self.report.target = self.request.target
			self.report.cycle = self.request.cycle
			self.report.plugin = self.request.plugin

class Report():
	'''Create a report event object to be injected into messaging infrastructure.
	A report can but does not have to be triggered by a request.'''
	def __init__(self,logging=None):
		'''Initialize event object creation.'''
		self.logging=logging
		self.UUID=str(uuid4())
		self.timezone=tzname[0]
		self.time=time()
		self.FQDN=node()
		self.sourceFQDN=self.FQDN
		self.requestUUID=None
		self.requestFQDN=None
		self.reason=None
		self.cycle=None
		self.subject=None
		self.destination={}
		self.target=None
		self.status='OK'
		self.message=None
		self.evaluators={}
		self.raw=None
		self.verbose=None
		self.metrics={}
		self.tags=[]
		self.format=None
		self.weight_map=None
		self.plugin=None
		self.pluginTimeout=None
		self.pluginHash=None		
		self.pluginParameters=None
		self.translator=Translate()
	def addEvaluator(self,name,status,value,metric,evaluator,thresholds):
		if not thresholds.has_key(status) and status != "OK":
			raise Exception("You define a non OK status while there is no such threshold defined.")
		self.evaluators[name]={ 'status':status,'value':value,'metric':metric,'evaluator':evaluator,'thresholds':thresholds}
	def __object(self):
		return {	'UUID':self.UUID,
				'requestUUID':self.requestUUID,
				'timezone':self.timezone,
				'time':self.time,
				'FQDN':self.FQDN,
				'sourceFQDN':self.sourceFQDN,
				'requestFQDN':self.requestFQDN,
				'reason':self.reason,
				'cycle':self.cycle,
				'subject':self.subject,
				'destination':self.destination,
				'target':self.target,
				'status':self.status,
				'message':self.message,
				'plugin':self.plugin,
				'pluginHash':self.pluginHash,
				'pluginTimeout':self.pluginTimeout,
				'pluginParameters':self.pluginParameters,
				'metrics':self.metrics,
				'evaluators':self.evaluators,
				'raw':self.raw,
				'verbose':self.verbose,
				'tags':self.tags,
				'format':self.format,
				'weight_map':self.weight_map}
	def construct(self,style='python'):
		if style == 'python':
			return self.__object()		
		elif style == 'json':
			try:
				return json.dumps(self.__object())
			except Exception as err:
				raise RuntimeError(err)
	def translate(self):
		return self.translator.do(self.construct())
class ReportRequest():
	def __init__(self,logging=None):
		self.variables = [ 'UUID','timezone','time','FQDN','type','reason','cycle','subject','destination','message','target',
				'plugin','pluginHash','pluginTimeout','pluginParameters','evaluators','tags','format','weight_map' ]
		for variable in self.variables:
			setattr(self,variable,None)
				
		#Assign default values to these variables
		self.UUID=str(uuid4())
		self.timezone=tzname[0]
		self.time=time()
		self.FQDN=node()
		self.type='reportRequest'
		
		self.logging=logging
	def addEvaluator(self,name,evaluator,thresholds):
		self.evaluators[name]={ 'evaluator':evaluator,'thresholds':thresholds}
	def __object(self):
		return {'UUID':self.UUID,
			'timezone':self.timezone,
			'time':self.time,
			'FQDN':self.FQDN,
			'type':self.type,
			'reason':self.reason,
			'cycle':self.cycle,
			'subject':self.subject,
			'destination':self.destination,
			'message':self.message,
			'target':self.target,
			'plugin':self.plugin,
			'pluginHash':self.pluginHash,
			'pluginTimeout':self.pluginTimeout,
			'pluginParameters':self.pluginParameters,
			'evaluators':self.evaluators,
			'weight_map':self.weight_map,
			'format':self.format,
			'tags':self.tags,
			'weight_map':self.weight_map}
	def construct(self,style='python'):
		if style == 'python':
			return self.__object()		
		elif style == 'json':
			try:
				return json.dumps(self.__object())
			except Exception as err:
				raise RuntimeError(err)
	def integrity(self,request=None):
		if request == None:
			request = self.construct()
		try:
			if not re.match('^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$',request['UUID']):
				raise InvalidReport( 'UUID is not valid.' )
			if request['timezone'] == '' or request['timezone'] == None:
				raise InvalidReport( 'timezone is not valid.' )
			if request['time'] == '' or request['time'] == None:
				raise InvalidReport( 'time is not valid.' )
			if request['FQDN'] == '' or request['FQDN'] == None:
				raise InvalidReport( 'FQDN is not valid.' )
			if request['type'] != 'systemRequest' and request['type'] != 'reportRequest':
				raise InvalidReport( 'type is not valid.' )
			if request['reason'] == '' or request['reason'] == None:
				raise InvalidReport( 'reason is not valid.' )
			if request['cycle'] < 0:
				raise InvalidReport( 'cycle is not valid.' )
			if request['subject'] == '' or request['subject'] == None:
				raise InvalidReport( 'subject is not valid.' )
			if request['destination'] == '' or request['destination'] == None or not str(type(request['destination'])) == "<type 'dict'>":
				raise InvalidReport( 'destination is not valid.' )
			if request['target'] == '' or request['target'] == None:
				raise InvalidReport( 'target is not valid.' )
			if request['plugin'] == '' or request['plugin'] == None:
				raise InvalidReport( 'plugin is not valid.' )
			if request['pluginHash'] == '' or request['pluginHash'] == None:
				raise InvalidReport( 'pluginHash has an invalid value.' )
			if request['pluginTimeout']  < 1:
				raise InvalidReport( 'pluginTimeout is not valid.' )
			if request['evaluators'] != '' or request['evaluators'] != None:
				if str(type(request['evaluators'])) != "<type 'dict'>":
					raise InvalidReport( 'Evaluators syntax is not correct.' )
				for evaluator in request['evaluators']:
					if str(type(request['evaluators'][evaluator])) != "<type 'dict'>":
						raise InvalidReport( 'Evaluators syntax is not a dictionary.' )
					if not request['evaluators'][evaluator].has_key("thresholds"):
						raise InvalidReport( 'Evaluators syntax does not contain thresholds.' )
					if not request['evaluators'][evaluator].has_key("evaluator"):
						raise InvalidReport( 'Evaluators syntax does not contain evaluator.' )
					if not request['evaluators'][evaluator].has_key("metric"):
						raise InvalidReport( 'Evaluators syntax does not contain metric.')
			request['message']
			request['pluginParameters']
			request['pluginHash']
			request['evaluators']
			request['tags']
			request['weight_map']
			request['format']			
			for variable in request:
				if variable not in self.variables:
					raise InvalidReport( 'Unknown data in request: %s'%(variable) )
		except Exception as error:
			raise Exception(error)
class SystemRequest():
	def __init__(self,logging=None):
		self.variables = [ 'UUID','timezone','time','FQDN','type','reason','cycle','subject','destination','target',
				'command','tags','message' ]
		for variable in self.variables:
			setattr(self,variable,None)

		self.UUID=str(uuid4())
		self.timezone=tzname[0]
		self.time=time()
		self.FQDN=node()
		self.message='Executing the system command %s did not return any feedback.'%(self.command)
		self.type='systemRequest'
		self.logging=logging
	def addCommand(self,command):
		#{'shutdown':'now'}
		#{'shutdown':'graceful'}
		#{'scheduler':'reset'}
		#{'upgrade': { 'plugin' : 'memory.py','source':'http://server' } }
		if command == {'shutdown':'now'}:
			self.command=command
		elif command == {'shutdown':'graceful'}:
			self.command=command
		elif command == {'scheduler':'reset'}:
			self.command=command
		else:
			raise Exception('Unknown command %s'%(command))
	def __object(self):
		return {'UUID':self.UUID,
			'timezone':self.timezone,
			'time':self.time,
			'FQDN':self.FQDN,
			'type':self.type,
			'reason':self.reason,
			'cycle':self.cycle,
			'subject':self.subject,
			'destination':self.destination,
			'message':self.message,
			'target':self.target,
			'command':self.command,
			'tags':self.tags}
	def construct(self,style='python'):
		if style == 'python':
			return self.__object()		
		elif style == 'json':
			try:
				return json.dumps(self.__object())
			except Exception as err:
				raise RuntimeError(err)
	def integrity(self,request=None):
		if request == None:
			request = self.construct()
		try:
			if not re.match('^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$',request['UUID']):
				raise InvalidReport( 'UUID is not valid.' )
			if request['timezone'] == '' or request['timezone'] == None:
				raise InvalidReport( 'timezone is not valid.' )
			if request['time'] == '' or request['time'] == None:
				raise InvalidReport( 'time is not valid.' )
			if request['FQDN'] == '' or request['FQDN'] == None:
				raise InvalidReport( 'FQDN is not valid.' )
			if request['type'] != 'systemRequest' and request['type'] != 'reportRequest':
				raise InvalidReport( 'type is not valid.' )
			if request['reason'] == '' or request['reason'] == None:
				raise InvalidReport( 'reason is not valid.' )
			if request['cycle'] < 0:
				raise InvalidReport( 'cycle is not valid.' )
			if request['subject'] == '' or request['subject'] == None:
				raise InvalidReport( 'subject is not valid.' )
			if request['destination'] == '' or request['destination'] == None or not str(type(request['destination'])) == "<type 'dict'>":
				raise InvalidReport( 'destination is not valid.' )
			if request['target'] == '' or request['target'] == None:
				raise InvalidReport( 'target is not valid.' )
			if request['command'] == '' or request['command'] == None:
				raise InvalidReport( 'command is not valid.' )
			request['message']
			request['tags']		
			for variable in request:
				if variable not in self.variables:
					raise InvalidReport( 'Unknown data in request: %s'%(variable) )
		except Exception as error:
			raise Exception(error)
class InvalidReport(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)
class Translate():
	'''Class for translating event.report objects into another format.'''
	def __init__(self):
		pass
	def do(self,report):
		if report['format'] == 'nagios:service' or report['format'] == 'nagios:host':
			return self.__nagios(report=report)
		else:
			return self.__json(report=report)
	def __json(self,report=None,sanitize=False):
		try:
			return json.dumps(report)
		except Exception as err:
			raise RuntimeError(err)
	def __nagios(self,report=None,sanitize=True):
		if report['verbose'] == None or report['verbose'] == '':
			message = self.__sanitize(data=report['message'],style='nagios')
		else:
			message = self.__sanitize(data="%s\\n<pre>%s</pre>"%(report['message'],report['verbose']),style='nagios')
		if len(report['evaluators'].keys()) > 0:
			performance_data='|'
			for evaluator in sorted(report['evaluators'].keys()):
				performance_data = "%s%s=%s;;;; "%(performance_data,evaluator,report['evaluators'][evaluator]['value'])
			performance_data = "%s [%s]"%(performance_data,report['subject'])
		else:
			performance_data=''
		
		
		if report['format'] == "nagios:service":
			translated_status='3'
			if report['status'] == None:
				report['status'] = 'unknown'
			if re.match(report['status'], 'ok', re.IGNORECASE):
				translated_status='0'
			elif re.match(report['status'], 'warning', re.IGNORECASE):
				translated_status='1'
			elif re.match(report['status'], 'critical', re.IGNORECASE):
				translated_status='2'
			elif re.match(report['status'], 'unknown', re.IGNORECASE):
				translated_status='3'
			elif report['status'] == None:
				translated_status == '3'
			return '[%s] PROCESS_SERVICE_CHECK_RESULT;%s;%s;%s;%s - %s%s'%(report['time'],report['target'],report['subject'],translated_status,report['status'],message,performance_data)
		elif report['format'] == "nagios:host":
			translated_status='3'
			if re.match(report['status'], 'up', re.IGNORECASE):
				translated_status='0'
			elif re.match(report['status'], 'updown', re.IGNORECASE):
				translated_status='1'
			elif re.match(report['status'], 'down', re.IGNORECASE):
				translated_status='2'
			elif re.match(report['status'], 'down', re.IGNORECASE):
				translated_status='3'
			elif report['status'] == None:
				translated_status == '3'				
			return '[%s] PROCESS_HOST_CHECK_RESULT;%s;%s;%s - %s%s'%(report['time'],report['target'],translated_status,report['status'],message,performance_data)
		else:
			return self.__json(report=report)
	def __sanitize(self,data=None,style=None):
		if style == 'nagios':
			data=data.replace('|','!')
			data=data.replace('<','*')
			data=data.replace('>','*')
			data=data.replace(';',':')
			data=data.replace('*pre*','<pre>')
			data=data.replace('*/pre*','</pre>')
			return data
		else:
			return data
		pass
