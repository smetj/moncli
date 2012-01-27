#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       engine.py
#       
#       Copyright 2011 Jelle Smet <development@smetj.net>
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
from urllib2 import urlopen
from apscheduler import scheduler
from warnings import simplefilter
from pika.adapters import SelectConnection
from socket import getfqdn
from moncli import event
from threading import Lock
from multiprocessing import Manager
from random import randint
from datetime import datetime, timedelta
from subprocess import Popen,PIPE
from tools import PluginManager
from tools import Calculator
from tools import StatusCalculator
from moncli.event2 import Request
import pika
import pickle
import json
import os
import time

simplefilter("ignore", "user")
class MoncliCommands():
    def __init__(self,scheduler_methods,logging=None):
        self.scheduler_methods=scheduler_methods
        self.logging=logging
    def execute(self,command):
        if command == {'system':'shutdown'}:
            self.__shutdown('now')
        if command == {'system':'graceful'}:
            self.__shutdown('graceful')
        if command == {'scheduler':'reset'}:
            self.__scheduler('reset')
        else:
            self.logging.put(['Error','Unknown command %s'%(command)])
    def __shutdown(self,data):
        if data == 'now':
            self.logging.put(['Normal','Immediate shutdown received. Bye'])
            time.sleep(2)
            os.kill(os.getpid(),9)
        if data == 'graceful':
            self.logging.put(['Normal','Graceful shutdown received. Bye'])
            time.sleep(2)
            os.kill(os.getpid(),2)      
    def __download(self,data):
        self.logging.put(['Normal','Download command received.'])
        filename=data.split('/')[-1]
        try:
            urlretrieve(data,filename)
        except:
            raise
    def __scheduler(self,data):
        if data == 'reset':
            self.logging.put(['Normal','Performing scheduler reset.'])
            self.scheduler_methods.reset()   
class Broker():
    '''Handles communication to message broker and initialises queus, exchanges and bindings if missing.'''
    def __init__(self,host,logger):
        self.queue_name = getfqdn()
        self.subnet_bind_key = '172.16.43.0/24'
        parameters = pika.ConnectionParameters(host)
        self.lock=Lock()
        self.properties = pika.BasicProperties(delivery_mode=2)
        self.connection = SelectConnection(parameters,self.__on_connected)
        self.connection.add_backpressure_callback(self.backpressure)
        self.addToScheduler=None
        self.logger=logger.get(name='Broker')
        self.logger.info('Broker started')
    def __on_connected(self,connection):
        self.logger.debug('Connecting to broker.')
        connection.channel(self.__on_channel_open)
    def __on_channel_open(self,new_channel):
        self.channel = new_channel
        self.__initialize()
        self.channel.basic_consume(self.processReportRequest, queue = self.queue_name)
    def __initialize(self):
        self.logger.debug('Creating exchanges, queues and bindings on broker.')
        self.channel.exchange_declare(exchange='moncli_report_requests_broadcast',type='fanout',durable=True)
        self.channel.exchange_declare(exchange='moncli_report_requests_subnet',type='direct',durable=True)
        self.channel.exchange_declare(exchange='moncli_report_requests',type='direct',durable=True)
        self.channel.exchange_declare(exchange='moncli_reports',type='fanout',durable=True)
        self.channel.queue_declare(queue=self.queue_name,durable=True)
        self.channel.queue_declare(queue='moncli_reports',durable=True)
        self.channel.queue_bind(queue=self.queue_name, exchange='moncli_report_requests_broadcast')
        self.channel.queue_bind(queue='moncli_reports', exchange='moncli_reports')
        self.channel.queue_bind(queue=self.queue_name, exchange='moncli_report_requests_subnet', routing_key=self.subnet_bind_key)
        self.channel.queue_bind(queue=self.queue_name, exchange='moncli_report_requests', routing_key=self.queue_name)
    def submitReportRequest(self,data):
        self.lock.acquire()
        self.logger.debug('Submitting a ReportRequest to moncli_report_requests')
        self.channel.basic_publish( exchange='moncli_report_requests', 
                        routing_key=self.queue_name, 
                        body=json.dumps(data), 
                        properties=pika.BasicProperties(delivery_mode=2)
                        )
        self.lock.release()
    def submitReport(self,data):
        print data
        self.lock.acquire()
        self.logger.debug('Submitting a Report to moncli_reports')
        self.channel.basic_publish( exchange='moncli_reports', 
                        routing_key='', 
                        body=json.dumps(data), 
                        properties=self.properties
                        )
        self.lock.release()
    def acknowledgeTag(self,tag):
        self.lock.acquire()
        self.logger.debug('Acknowledging Tag.')
        self.channel.basic_ack(delivery_tag=tag)
        self.lock.release()
    def processReportRequest(self,ch, method, properties, body):
        try:
            data = json.loads(body)
            Request.validate(data=data)
        except Exception as err:
            self.logger.warn('Garbage reveived from broker, purging. Reason: %s'%(err))
            self.acknowledgeTag(tag=method.delivery_tag)
        else:
            self.addToScheduler(data)
            self.acknowledgeTag(tag=method.delivery_tag)
    def backpressure(self):
        self.logger.debug('Backpressure detected.')
class PluginExecute():
    '''Verifies and executes a plugin and keeps track of its cache'''
    def __init__(self,caching=False):
        self.output=None
        self.verbose=None
        self.dictionary=None
        self.caching=caching
        self.cache=Manager().dict()
    def do(self,command=None,parameters=None,hash=None,timeout=30):
        normal_output=[]
        error_output=[]
        errors=None
        
        if parameters == None or parameters == '':
            command=command
        else:
            command = "%s %s"%(command,parameters)
        shell = Popen(command, shell=True, bufsize=0,stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
        (child_stdin, child_stdout, child_stderr) = (shell.stdin, shell.stdout,shell.stderr)    
        start=time.time()
        endtime=int(start)+int(timeout)     
        while (shell.poll()==None) and (time.time()<endtime):
            time.sleep(0.5)
            pass    
        if (shell.poll()==None):
            shell.kill()
            raise RuntimeError("The plugin was killed after running for %s seconds" %(timeout))
        else:
            totaltime=time.time()-start 
            for line in child_stdout:
                normal_output.append(line.rstrip('\n'))
            for line in child_stderr:
                error_output.append(line.rstrip('\n'))
        if len(error_output) != 0:
            raise RuntimeError("The plugin returned errors :"+'\n'.join(error_output))
        
        (output,verbose,dictionary)=self.__splitOutput(data=normal_output)
        dictionary["epoch"]=round(time.time())
        dictionary=self.__cache(plugin=command,dictionary=dictionary)
        
        return (output,verbose,dictionary)
    def __splitOutput(self,data):
        data=data
        output=[]
        verbose=[]
        dictionary={}
        while len(data)  != 0:
            line = data.pop(0)
            if str(line) == '~==.==~':
                verbose='\\n'.join(data)
                break
            else:
                output.append(line)
                try:
                    key_value=line.split(":")
                    dictionary[key_value[0]]=key_value[1]
                except:
                    pass
        return (output,verbose,dictionary)
    def __cache(self,plugin,dictionary):
        current_dictionary          = dictionary
        cache_dictionary            = self.cache.get(plugin,current_dictionary)
        self.cache[plugin]          = dictionary
        for value in cache_dictionary:
            current_dictionary['pre_'+value]=cache_dictionary[value]
        return current_dictionary
class BuildMessage():
    '''Builds human readable summary messages by replacing variables in request.message with their value.'''
    def __init__(self):
        pass
    def generate(self,evaluators,message):
        for evaluator in evaluators:
            message=message.replace('#'+str(evaluator),'(%s) %s'%(evaluators[evaluator]['status'],evaluators[evaluator]['value']))
        return message
class JobScheduler():
    def __init__(self,logger):
        self.logger=logger
        self.sched=scheduler.Scheduler()
        self.submitBroker=None
        self.sched.start()
        self.request={}        
        self.do_lock=Lock()
    def do(self,doc):
        self.do_lock.acquire()
        name = self.__name(doc)
        if self.request.has_key(name):
            self.__unschedule(name=name, object = self.request[name][scheduler])
        if doc['request']['cycle'] == 0:
            self.logger.debug ('Executed imediately job %s'%(name))
            job=ReportRequestExecutor(local_repo='/opt/moncli/lib/repository',remote_repo='http://blah',logger=self.logger)
            job.do(doc=doc)
        else:
            self.__schedule(doc=doc)
        self.do_lock.release()
    def __unschedule(self,name,object):
        self.logger.debug ('Unscheduled job %s'%(name))
        self.sched.unschedule_job(object)
        del self.request[name]        
    def __register(self,doc):
        name = self.__name(doc)
        self.logger.debug ('Registered job %s'%(name))
        self.request[name]={ 'function' : None, 'scheduler': None }
        self.request[name]['function']=ReportRequestExecutor2(local_repo='/opt/moncli/lib/repository',
                                                    remote_repo='http://blah',
                                                    submitBroker=self.submitBroker,
                                                    logger=self.logger)        
    def __schedule(self,doc):
        name = self.__name(doc)
        self.logger.debug ('Scheduled job %s'%(name))
        random_wait = randint(1,int(60))
        self.__register(doc)
        self.request[name][scheduler]=self.sched.add_interval_job( self.request[name]['function'].do,
                                                        seconds=int(doc['request']['cycle']),
                                                        name = name,
                                                        start_date=datetime.now()+timedelta(0,random_wait),
                                                        kwargs = { 'doc':doc })
    def __name(self,doc):
        return '%s:%s'%(doc['destination']['name'],doc['destination']['subject'])
class ReportRequestExecutor():
    def __init__(self,local_repo, remote_repo,submitBroker,logger):
        self.pluginManager = PluginManager( local_repository = local_repo,
                                remote_repository = remote_repo,
                                logger = logger)
        self.pluginExecute=PluginExecute(caching=True)
        self.calculator = Calculator()
        self.submitBroker=submitBroker
        self.logger = logger
    def do(self,doc):
        request = Request(doc=doc)
        self.logger.info('Executing a request with destination %s:%s'%(doc['destination']['name'],doc['destination']['subject']))
        
        #Get plugin to execute
        command = self.pluginManager.getExecutable(command=request.plugin['name'],hash=request.plugin['hash'])
        
        #Execute the plugin
        (request.answer['plugin']['raw'],
        request.answer['plugin']['verbose'],
        request.answer['plugin']['metrics']) = self.pluginExecute.do( command=command,
                                                    parameters=request.plugin['parameters'],
                                                    hash=request.plugin['hash'],
                                                    timeout=request.plugin['timeout'] )

        #Calculate each evaluator
        request.calculate()
        self.submitBroker(request.answer)
