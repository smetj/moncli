#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       tools.py
#       
#       Copyright 2011 Jelle Smet<development@smetj.net>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 3 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
#       
#
from __future__ import division
from platform import system,machine
from hashlib import md5
from urllib2 import urlopen
import logging
import os
import re
#import yappi
        
class Calculator():
 
    def __init__(self):
        self.logging = logging.getLogger(__name__)
        self.whitelist=[ '+','-','/','*','^','(',')','.',' ' ]
 
    def do(self,output,dictionary,evaluator,thresholds):
        if evaluator[:3] == 're:':
            value = self.__ShellExecuteegex(output=output,regex=evaluator[3:])
        elif evaluator[:3] == 'fm:':
            value = self.__executeFormula(dictionary=dictionary,formula=evaluator[3:])
        else:
            raise RuntimeError("The evaluator does not start with a known type: %s" %(evaluator))
        status = self.__evaluateThresholds(thresholds=thresholds,value=value)
        return (value,status)
 
    def __executeFormula(self,dictionary,formula):
        for key, val in dictionary.items():
            formula = re.sub('(\+|-|\/|\*|\^|\(|\)|\s|^)'+key+'(?=\+|-|\/|\*|\^|\(|\)|\s|\n|$)','\\1 '+str(val),formula)
        to_evaluate=re.findall('\D',formula)
        to_evaluate=list(set(to_evaluate))
        for element in to_evaluate:
            if not element in self.whitelist:
                raise RuntimeError("Error in the evaluator formula: %s" %(formula))
        try:
            result= round(eval(str(formula)),2)
        except:
            result= None
        return result
 
    def __ShellExecuteegex(self,output,regex):
        matches=0
        try:
            for line in output:
                if re.search(regex,line):
                    matches+=1
                    evaluator=matches
            return matches
        except:
            raise RuntimeError("Error in the eveluator regex: %s" %(evaluator))
 
    def __evaluateThresholds(self,thresholds,value):
        ''' Nagios threshold definitions
            1)  10          < 0 or > 10, (outside the range of {0 .. 10})
            2)  10:         < 10, (outside {10 .. ~})
            3)  ~:10        > 10, (outside the range of {-~ .. 10})
            4)  10:20       < 10 or > 20, (outside the range of {10 .. 20})
            5)  @10:20      >= 10 and <= 20, (inside the range of {10 .. 20})
        '''
        evaluator_1=re.compile('(^\d*$)')
        evaluator_2=re.compile('(^\d*?):$')
        evaluator_3=re.compile('^~:(\d*)')
        evaluator_4=re.compile('(\d*):(\d*)')
        evaluator_5=re.compile('^@(\d*):(\d*)')
        for threshold in thresholds:
            if evaluator_1.match(thresholds[threshold]):
                number=evaluator_1.match(thresholds[threshold])
                if int(value) < 0 or int(value) > int(number.group(1)):
                    return threshold
            elif evaluator_2.match(thresholds[threshold]):
                number=evaluator_2.match(thresholds[threshold])
                if int(value) < int(number.group(1)):
                    return threshold
            elif evaluator_3.match(thresholds[threshold]):
                number=evaluator_3.match(thresholds[threshold])
                if int(value) < int(number.group(1)):
                    return threshold
            elif evaluator_4.match(thresholds[threshold]):
                number=evaluator_4.match(thresholds[threshold])
                if int(value) < int(number.group(1)) or int(value) > int(number.group(2)):
                    return threshold
            elif evaluator_5.match(thresholds[threshold]):
                number=evaluator_5.match(thresholds[threshold])
                if int(value) >= int(number.group(1)) and int(value) <= int(number.group(2)):
                    return threshold
            else:
                raise RuntimeError('Invalid Threshold :'+str(threshold))
        return "OK"


class StatusCalculator():
    '''Contains a number of methods facilitating different kind of status calculations.'''

    def __init__(self,weight_map='default',template=None):
        self.logging = logging.getLogger(__name__)
        if weight_map == 'nagios:service':
            self.template=self.__setNagiosService()
        elif weight_map == 'nagios:host':
            self.template=self.__setNagiosHost()
        else:
            self.template=self.__setDefault()
        self.states=[]

    def result(self):
        results={}
        for state in self.states:
            if self.__templateContainsName(name=state,template=self.template):
                if not results.has_key(state):
                    results[state]=0
                results[state]+=1
        for key in sorted(self.template.iterkeys(),reverse=True):
            if results.has_key(self.template[key]['name']) and results[self.template[key]['name']] >= self.template[key]['weight'] :
                return self.template[key]['name']
        return self.template[sorted(self.template.iterkeys(),reverse=True)[0]]['name']

    def __setDefault(self):
        return {    0: { 'name': 'OK', 'weight': 1}, 
                    1: { 'name': 'warning', 'weight': 1},
                    2: { 'name': 'critical', 'weight': 1},
                    3: { 'name': 'unknown', 'weight': 1} }

    def __setNagiosService(self):
        return {    0: { 'name': 'OK', 'weight': 1}, 
                    1: { 'name': 'warning', 'weight': 1},
                    2: { 'name': 'critical', 'weight': 1},
                    3: { 'name': 'unknown', 'weight': 1} }

    def __setNagiosHost(self):
        return {    0: { 'name': 'OK', 'weight': 1}, 
                    1: { 'name': 'updown', 'weight': 1},
                    2: { 'name': 'down', 'weight': 1},
                    3: { 'name': 'down', 'weight': 1} }

    def __templateContainsName(self,name,template):
        for element in template:
            if template[element]['name'] == name:
                return True
        return False


class PluginManager():
    '''Provides the name of the plugin to execute, verifies its hash and downloads a new plugin version if required.'''
    
    def __init__(self,local_repository,remote_repository):
        self.logging = logging.getLogger(__name__)
        self.local_repository=local_repository
        self.remote_repository=remote_repository
        if self.local_repository[-1] != '/':
            self.local_repository += '/'
        if self.remote_repository != None and self.remote_repository[-1] != '/':
            self.remote_repository += '/'
        self.logging.debug('PluginManager Initiated')

    def getExecutable(self,command,hash=None):
        if not os.path.exists(self.local_repository+command):
            self.__createCommand(dir=self.local_repository+command)         
        if not os.path.isfile(self.local_repository+command+'/'+hash) and self.remote_repository != '':
            self.__downloadVersion(self.remote_repository,self.local_repository,command,hash)
        if self.__checkHash(fullpath=self.local_repository+'/'+command+'/'+hash,file=hash) == True:
            return self.local_repository+'/'+command+'/'+hash

    def __checkHash(self,fullpath,file):
        plugin = open(fullpath,'r')
        plugin_hash = md5()
        plugin_hash.update((''.join(plugin.readlines())))
        plugin.close()
        if file != plugin_hash.hexdigest():
            raise Exception ( 'Plugin filename does not match its hash value.' )
            self.logging.warning ( 'Plugin filename %s does not match its hash value %s.'%(file,plugin_hash.hexdigest() ) )
        return True 

    def __createCommand(self,dir):
        os.mkdir(dir)

    def __downloadVersion(self,remote_repository,local_repository,command,hash):
        full_url = "%s%s(%s)/%s/%s"%(remote_repository,system(),machine(),command,hash)
        self.logging.info ('Downloading update %s.'%(full_url))
        try:
            response = urlopen(full_url)
        except Exception as err:
            self.logging.critical ( 'Error downloading update. Reason: %s'%(str(err) + " - "+full_url) )
            raise Exception (str(err) + " - "+full_url )
            
        output = open ( local_repository+'/'+command+'/'+hash, 'w' )
        output.write(response.read())
        response.close()
        output.close()
        #Make executable
        os.chmod(local_repository+'/'+command+'/'+hash,0750)


class Profile():
    '''Used for profiling purposes'''

    def __init__(self):
        yappi.start()
        self.yappi_results = open ( '/opt/moncli/var/profile.yappi','w' )

    def write(self):
        for line in yappi.get_stats(    yappi.SORTTYPE_TTOTAL,
                        yappi.SORTORDER_ASCENDING,
                        yappi.SHOW_ALL):
            self.yappi_results.write(line+"\n")
            print line


def logger(file=None,loglevel=logging.INFO):
        format=('%(asctime)s %(levelname)s %(name)s %(message)s')
        if file == None:
            logging.basicConfig(level=loglevel, format=format)
        else:
            print file
            logging.basicConfig(filename=file, level=loglevel, format=format)
