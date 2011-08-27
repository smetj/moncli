#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       logic.py
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


class nagios_logic:
	def __init__(self):
		pass
	def worst_state(self,ok=True,warning=False,critical=False,unknown=False):
		if critical == True:
			return "2"
		elif warning == True:
			return "1"
		elif unknown == True:
			return "3"
		else:
			return "0"
	def number_based_state(self,numeric=True,warnings=0,criticals=0):
		'''Returns nagios state based on the amount of warnings or criticals.'''
		warning=False
		critical=False
		if warnings > 0:
			warning=True
		if criticals > 0:
			critical=True
		if numeric==True:
			return self.worst_state(warning=warning,critical=critical)
		else:
			return self.translate_code(state=self.worst_state(warning=warning,critical=critical))
	def translate_code(self,state=None):
		if state=='0':
			return 'ok'
		elif state=='1':
			return 'warning'
		elif state=='2':
			return 'critical'
		else:
			return 'unknown'
