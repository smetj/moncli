#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       format_message.py
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

import time
from xml.sax.saxutils import escape

class construct_bulk:
	def __init__(self,type):
		'''construct bulk expects a list of dictionaries with following keys:
			type					The type of check (service/host)
			hostname				The hostname
			servicename				The servicename
			global_exit_code		The exit code
			message					The message appearing on the interface
			plugin_verbose_ouput	The extra output
			perfdata				Performance data.
		'''
		self.type=type
		self.handler=None
		if self.type=='nagios' or self.type=='nscaweb' or self.type=='local' or type == 'file':
			self.handler=nagios_format()
		elif self.type=='nrdp':
			self.handler=nrdp_format()
	def do(self,data=None):
		return self.handler.generate(data=data)
class construct_bulk2():
	def __init__(self):
		pass
	def do(self,data=None,type=None):
		if type=='nagios' or type=='nscaweb' or type=='local' or type =='file' or type=='pipe':
			handler=nagios_format()
		elif type=='nrdp':
			handler=nrdp_format()
		return handler.generate(data=data)
class sanitize():
	def __init__(self):
		pass
	def remove_illegal_chars(self,data):
		if data != None:
			data=data.replace('|','!')
			data=data.replace('<','*')
			data=data.replace('>','*')
		return data
	def add_pre_tags(self,data):
		if data != None:
			data='<pre>'+data+'</pre>'
		return data
class nagios_format:
	def __init__(self):
		self.filter=sanitize()
	def generate(self,data=None):
		if data != None:
			results=[]
			for package in data:
				if package.has_key('plugin_verbose_output') and package['plugin_verbose_output'] != '' and package['plugin_verbose_output'] != None:
					package['plugin_verbose_output']=self.filter.remove_illegal_chars(package['plugin_verbose_output'])
					package['plugin_verbose_output']=self.filter.add_pre_tags(package['plugin_verbose_output'])
					package['plugin_verbose_output']='\\n'+package['plugin_verbose_output']
				if package.has_key('perfdata') and package['perfdata'] != '' and package['perfdata'] != None:
					package['perfdata']='|'+package['perfdata']
				if (package.has_key('type') and package['type']=='service'):
					results.append('[%s] PROCESS_SERVICE_CHECK_RESULT;%s;%s;%s;%s%s%s'%(time.time(),package['hostname'],package['servicename'],package['global_exit_code'],package['message'],package['plugin_verbose_output'],package.get('perfdata','')))
				if (package.has_key('type') and package['type']=='host'):
					results.append('[%s] PROCESS_HOST_CHECK_RESULT;%s;%s;%s%s%s'%(time.time(),package['hostname'],package['global_exit_code'],package['message'],package['plugin_verbose_output'],package.get('perfdata','')))
			if len(results)==1:
				return results[0]
			else:
				return '\n'.join(results)
		return None
class nrdp_format:
	def __init__(self):
		self.filter=sanitize()
	def generate(self,data=None):
		results=["<?xml version='1.0'?>\n<checkresults>"]
		for package in data:
			if package.has_key('plugin_verbose_output') and package['plugin_verbose_output'] != '' and package['plugin_verbose_output'] != None:
					package['plugin_verbose_output']=self.filter.remove_illegal_chars(package['plugin_verbose_output'])
					package['plugin_verbose_output']=self.filter.add_pre_tags(package['plugin_verbose_output'])
					package['plugin_verbose_output']='\\n'+package['plugin_verbose_output']
			if package.has_key('perfdata') and package['perfdata'] != '' and package['perfdata'] != None:
					package['perfdata']='|'+package['perfdata']
			try:		
				package['plugin_verbose_output'] = escape(package['plugin_verbose_output'])
			except:
				pass
					
			try:
				package['message'] = escape(package['message'])
			except:
				pass

			if package['type']=='service':
				results.append(self.__process_service_check_result(hostname=package['hostname'],servicename=package['name'],state=package['global_exit_code'],message=package['message'],verbose=package['plugin_verbose_output'],perfdata=package['perfdata']))
			if package['type']=='host':
				results.append(self.__process_host_check_result(hostname=package['hostname'],state=package['global_exit_code'],message=package['message'],verbose=package['plugin_verbose_output'],perfdata=package['perfdata']))
		results.append("</checkresults>")
		return '\n'.join(results)
	def __process_service_check_result(self,hostname=None,servicename=None,state=None,message=None,verbose=None,perfdata=None):
		return 	"\t<checkresult type='service'>\n\t<hostname>%s</hostname>\n\t<servicename>%s</servicename>\n\t<state>%s</state>\n\t<output>%s%s%s</output>\n\t</checkresult>"%(hostname,servicename,state,message,verbose,perfdata)
	def __process_host_check_result(self,hostname=None,state=None,message=None,verbose=None,perfdata=None):
		return 	"\t<checkresult type='host'>\n\t<hostname>%s</hostname>\n\t<state>%s</state>\n\t<output>%s%s%s</output>\n\t</checkresult>"%(hostname,state,message,verbose,perfdata)		
