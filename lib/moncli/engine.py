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
class JobScheduler():
    def __init__(self,config,logger):
        self.config=config
        self.logger=logger.get(name='JobScheduler')
        self.produceReport=None
        self.jobs={}
        self.job_refs={}
        scheduler.logger=self.logger
        self.sched = scheduler.Scheduler()
        self.sched.add_interval_job(self.save,seconds=10,name='Cache saving.')
        self.pluginExecute=PluginExecute(caching=True)
        self.do_lock=Lock()
    def do(self,data):
        self.do_lock.acquire()
        name = '%s:%s'%(data['target'],data['subject'])
        if int(data['cycle']) > 0:
            if self.jobs.has_key(name):
                self.logger.debug ('Already a job with name %s exits, deleting from scheduler.'%name)
                self.deleteJob(name)
            else:
                self.jobs.update({name:data})
                
            random_wait = randint(1,int(self.config['rand_window']))
            self.logger.debug ( "Generated an initial random wait of %s seconds for job %s."%(random_wait,name) )
            self.job_refs[name]=self.sched.add_interval_job(    self.reportRequestExecutor,
                                        seconds=int(data['cycle']),
                                        name = name,
                                        start_date=datetime.now()+timedelta(0,random_wait),
                                        kwargs = { 'data':data }
                                        )
        else:
            if self.jobs.has_key(name):
                self.deleteJob(name)
            self.reportRequestExecutor(data)
        self.do_lock.release()
    def deleteJob(self,name):
        self.sched.unschedule_job(self.job_refs[name])
        del(self.jobs[name])
        del(self.job_refs[name])        
    def submit(self,data):
        self.rx_queue.put(data)
    def shutdown(self):
        self.save()     
        self.sched.shutdown()
    def save(self):
        try:
            output=open(self.config['cache'],'wb')
            pickle.dump(self.jobs,output)
            output.close()
            self.logger.info('Job scheduler: Moncli cache file saved.')
        except Exception as err:
            self.logger.warn('Job scheduler: Moncli cache file could not be saved. Reason: %s.'%(err))
    def load(self):
        try:
            input=open(self.config['cache'],'r')
            jobs=pickle.load(input)
            input.close()
            for job in jobs:
                self.do(data=jobs[job])
            self.jobs=jobs
            self.logger.info('Job scheduler: Loaded cache file.')
        except Exception as err:
            self.logger.info('Job scheduler: I could not open cache file: Reason: %s.'%(err))
    def reset(self):
        for job in self.jobs:
            self.sched.unschedule_job(self.jobs[job])
            del(self.jobs[job])
    def reportRequestExecutor(self,data):
        pluginManager=PluginManager(    local_repository    = self.config['local_repository'],
                        remote_repository   = self.config['remote_repository'],
                        logger          = self.logger
                        )
        execute = ReportRequestExecutor (   request= data,
                            pluginManager= pluginManager,
                            pluginExecute= self.pluginExecute,
                            logger= self.logger,
                            submitReport= self.produceReport
                            )
class Broker():
    '''Handles communication to message broker and initialises queus, exchanges and bindings if missing.'''
    def __init__(self,host,logger):
        self.queue_name = getfqdn()
        self.subnet_bind_key = '172.16.43.0/24'
        parameters = pika.ConnectionParameters(host)
        self.request = event.ReportRequest()
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
            self.request.integrity(request=data)
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
class ReportRequestExecutor():
    '''A worker processes receives and executes an incoming request, creates a report, reschedules it if required and submits it to output queue.'''
    def __init__(self,request,pluginManager,pluginExecute,logger,submitReport):
        self.request=request
        self.pluginManager=pluginManager
        self.pluginExecute=pluginExecute
        self.submitReport=submitReport
        self.moncli_commands=MoncliCommands
        
        self.logger=logger
    
        self.calculator = Calculator()  

        self.event = event.Event()
        document = self.request
        try:
            self.event.loadRequest(document)
        except Exception as error:
            self.logger.warn('Junk package received. Reason: %s.'%(error))
        else:
            if self.event.request.type == 'reportRequest':
                try:
                    self.logger.info('Worker received a request type report named %s.%s'%(self.event.request.subject,self.event.request.target))
                    #Get plugin
                    command = self.pluginManager.getExecutable(command=document['plugin'],hash=document['pluginHash'])
                    #Execute plugin
                    (self.event.report.raw,self.event.report.verbose,self.event.report.metrics) = self.pluginExecute.do(    command=command,
                                                                parameters=self.event.request.pluginParameters,
                                                                hash=self.event.request.pluginHash,
                                                                timeout=self.event.request.pluginTimeout)
                    #Calculate each evalutor and global status
                    global_status = StatusCalculator(weight_map=self.event.request.weight_map)
                    for evaluator in self.event.request.evaluators:
                        (value,status)  = self.calculator.do(   output=self.event.report.raw,
                                            dictionary=self.event.report.metrics,
                                            evaluator=self.event.request.evaluators[evaluator]['evaluator'],
                                            thresholds=self.event.request.evaluators[evaluator]['thresholds'])
                            
                        self.event.report.addEvaluator( name=evaluator,
                                        status=status,
                                        value=value,
                                        metric=self.event.request.evaluators[evaluator].get('metric',None),
                                        evaluator=self.event.request.evaluators[evaluator]['evaluator'],
                                        thresholds=self.event.request.evaluators[evaluator]['thresholds'])
                                
                        global_status.states.append(status)                             
            
                        self.event.report.status=global_status.result()
                            
                        #Replace placeholders in message with values.
                        message=BuildMessage()
                        self.event.report.message=message.generate(evaluators=self.event.report.evaluators,message=self.event.request.message)
                        
                        #Finalize the report
                        self.event.finalizeReport()                                                         
                except Exception as err:
                    self.logger.critical('An error occured processing "%s" Reason: %s'%(self.event.request.subject,err))
                    self.event.report.status = None
                    self.event.report.message=str(type(err))+" "+str(err)
                    self.event.finalizeReport() 
                self.submitReport (self.event.report.translate())
            elif self.event.request.type == 'systemRequest':
                try:
                    self.moncli_commands.execute(command=self.event.request.command)
                    self.logger.info('Worker received a request type system.')
                except Exception as err:
                    self.logger.critical('An error occured processing "%s" Reason: %s'%(self.event.request.subject,err))
                    self.event.report.status = None
                    self.event.report.message=str(type(err))+" "+str(err)
                
                self.event.finalizeReport()
                self.submitReport (self.event.report.translate())
            else:
                self.logger.critical('Junk package received but not noticed by verification routine. Please report to developer.'%(self.name))      
