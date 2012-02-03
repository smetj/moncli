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
from random import randint
from datetime import datetime, timedelta
from subprocess import Popen, STDOUT, PIPE
from tools import PluginManager
from tools import Calculator
from tools import StatusCalculator
from moncli.event import Request
import threading
import pika
import pickle
import json
import os
import time
import logging



simplefilter("ignore", "user")


class MoncliCommands():
    def __init__(self, scheduler_methods):
        self.scheduler_methods = scheduler_methods
        self.logging=logging.getLogger(__name__)

    def execute(self, command):
        if command == {'system': 'shutdown'}:
            self.__shutdown('now')
        if command == {'system': 'graceful'}:
            self.__shutdown('graceful')
        if command == {'scheduler': 'reset'}:
            self.__scheduler('reset')
        else:
            self.logging.put(['Error', 'Unknown command %s' % (command)])

    def __shutdown(self, data):
        if data == 'now':
            self.logging.put(['Normal', 'Immediate shutdown received. Bye'])
            time.sleep(2)
            os.kill(os.getpid(), 9)
        if data == 'graceful':
            self.logging.put(['Normal', 'Graceful shutdown received. Bye'])
            time.sleep(2)
            os.kill(os.getpid(), 2)

    def __download(self, data):
        self.logging.put(['Normal', 'Download command received.'])
        filename = data.split('/')[-1]
        try:
            urlretrieve(data, filename)
        except:
            raise

    def __scheduler(self, data):
        if data == 'reset':
            self.logging.put(['Normal', 'Performing scheduler reset.'])
            self.scheduler_methods.reset()


class Broker():
    '''Handles communication to message broker and initialises queus, exchanges and bindings if missing.'''

    def __init__(self, host):
        self.queue_name = getfqdn()
        self.subnet_bind_key = '172.16.43.0/24'
        self.parameters = pika.ConnectionParameters(host)
        self.properties = pika.BasicProperties(delivery_mode=2)
        self.connection = None
        self.addToScheduler = None
        self.reconnect = None
        self.logging = logging.getLogger(__name__)
        self.logging.info('Broker started')
        self.__start_connect()
        self.lock = Lock()

    def __start_connect(self):
        self.connection = SelectConnection(self.parameters, self.__on_connected)
        self.connection.add_backpressure_callback(self.backpressure)

    def __on_connected(self, connection):
        self.logging.debug('Connecting to broker.')
        connection.channel(self.__on_channel_open)

    def __on_channel_open(self, new_channel):
        self.channel = new_channel
        self.__initialize()
        self.channel.basic_consume(self.processReportRequest, queue=self.queue_name)

    def __initialize(self):
        self.logging.debug('Creating exchanges, queues and bindings on broker.')
        self.channel.exchange_declare(exchange='moncli_report_requests_broadcast', type='fanout', durable=True)
        self.channel.exchange_declare(exchange='moncli_report_requests_subnet', type='direct', durable=True)
        self.channel.exchange_declare(exchange='moncli_report_requests', type='direct', durable=True)
        self.channel.exchange_declare(exchange='moncli_reports', type='fanout', durable=True)
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        self.channel.queue_declare(queue='moncli_reports', durable=True)
        self.channel.queue_bind(queue=self.queue_name, exchange='moncli_report_requests_broadcast')
        self.channel.queue_bind(queue='moncli_reports', exchange='moncli_reports')
        self.channel.queue_bind(queue=self.queue_name, exchange='moncli_report_requests_subnet', routing_key=self.subnet_bind_key)
        self.channel.queue_bind(queue=self.queue_name, exchange='moncli_report_requests', routing_key=self.queue_name)

    def submitReportRequest(self, data):
        self.lock.acquire()
        self.logging.debug('Submitting a ReportRequest to moncli_report_requests')
        self.channel.basic_publish(exchange='moncli_report_requests',
                        routing_key=self.queue_name,
                        body=json.dumps(data),
                        properties=pika.BasicProperties(delivery_mode=2))
        self.lock.release()

    def submitReport(self, data):
        self.lock.acquire()
        self.logging.debug('Submitting a Report to moncli_reports')
        self.channel.basic_publish(exchange='moncli_reports',
                        routing_key='',
                        body=json.dumps(data),
                        properties=self.properties)
        self.lock.release()

    def acknowledgeTag(self, tag):
        self.lock.acquire()
        self.logging.debug('Acknowledging Tag.')
        self.channel.basic_ack(delivery_tag=tag)
        self.lock.release()

    def processReportRequest(self, ch, method, properties, body):
        try:
            data = json.loads(body)
            Request.validate(data=data)
        except Exception as err:
            self.logging.warn('Garbage reveived from broker, purging. Reason: %s' % (err))
            self.acknowledgeTag(tag=method.delivery_tag)
        else:
            self.addToScheduler(data)
            self.acknowledgeTag(tag=method.delivery_tag)

    def backpressure(self):
        self.logging.debug('Backpressure detected.')


class BuildMessage():
    '''Builds human readable summary messages by replacing variables in request.message with their value.'''

    def __init__(self):
        self.logging = logging.getLogger(__name__)

    def generate(self, evaluators, message):
        for evaluator in evaluators:
            message = message.replace('#' + str(evaluator), '(%s) %s' % (evaluators[evaluator]['status'], evaluators[evaluator]['value']))
        return message


class JobScheduler():

    def __init__(self, cache_file, local_repo, remote_repo):
        self.logging = logging.getLogger(__name__)
        self.sched = scheduler.Scheduler()
        self.submitBroker = None
        self.request = {}
        self.cache_file = cache_file
        self.local_repo=local_repo
        self.remote_repo=remote_repo
        self.do_lock = Lock()
        self.sched.start()

    def do(self, doc):
        self.do_lock.acquire()
        name = self.__name(doc)
        if self.request.has_key(name):
            self.__unschedule(name=name, object=self.request[name]['scheduler'])
        if doc['request']['cycle'] == 0:
            self.logging.debug('Executed imediately job %s' % (name))
            job = ReportRequestExecutor(local_repo=self.local_repo, remote_repo=self.remote_repo)
            job.do(doc=doc)
        else:
            self.__schedule(doc=doc)
        self.__save()
        self.do_lock.release()

    def __unschedule(self, name, object):
        self.logging.debug('Unscheduled job %s' % (name))
        self.sched.unschedule_job(object)
        del self.request[name]

    def __register(self, doc):
        name = self.__name(doc)
        self.logging.debug('Registered job %s' % (name))
        self.request[name] = {'function': None, 'scheduler': None, 'document': None}
        self.request[name]['document'] = doc
        self.request[name]['function'] = ReportRequestExecutor(local_repo='/opt/moncli/lib/repository',
                                                    remote_repo='http://blah',
                                                    submitBroker=self.submitBroker)

    def __schedule(self, doc):
        name = self.__name(doc)
        self.logging.debug('Scheduled job %s' % (name))
        random_wait = randint(1, int(60))
        self.__register(doc)
        self.request[name]['scheduler'] = self.sched.add_interval_job(self.request[name]['function'].do,
                                                        seconds=int(doc['request']['cycle']),
                                                        name=name,
                                                        start_date=datetime.now() + timedelta(0, random_wait),
                                                        kwargs={'doc': doc})

    def __name(self, doc):
        return '%s:%s' % (doc['destination']['name'], doc['destination']['subject'])

    def __save(self):
        try:
            output = open(self.cache_file, 'wb')
            cache = []
            for doc in self.request:
                cache.append(self.request[doc]['document'])
            pickle.dump(cache, output)
            output.close()
            self.logging.info('Job scheduler: Moncli cache file saved.')
        except Exception as err:
            self.logging.warn('Job scheduler: Moncli cache file could not be saved. Reason: %s.' % (err))

    def load(self):
        try:
            input = open(self.cache_file, 'r')
            jobs = pickle.load(input)
            input.close()
            for job in jobs:
                self.__schedule(doc=job)
            self.logging.info('Job scheduler: Loaded cache file.')
        except Exception as err:
            self.logging.info('Job scheduler: I could not open cache file: Reason: %s.' % (err))

    def shutdown(self):
        self.sched.shutdown()


class ReportRequestExecutor():
    '''Don't share this class over multiple threads/processes.'''

    def __init__(self, local_repo, remote_repo, submitBroker):
        self.logging = logging.getLogger(__name__)
        self.pluginManager = PluginManager(local_repository=local_repo,
                                remote_repository=remote_repo)
        self.executePlugin = ExecutePlugin()
        self.submitBroker = submitBroker
        self.cache = {}

    def do(self, doc):
        try:
            self.logging.info('Executing a request with destination %s:%s' % (doc['destination']['name'], doc['destination']['subject']))
            request = Request(doc=doc)
            command = self.pluginManager.getExecutable(command=request.plugin['name'], hash=request.plugin['hash'])
            output = self.executePlugin.do(request.plugin['name'], command, request.plugin['parameters'], request.plugin['timeout'])
            (raw, verbose, metrics) = self.processOutput(request.plugin['name'],output)
            # metrics
            request.insertPluginOutput(raw, verbose, metrics)            
            self.submitBroker(request.answer)
        except Exception as err:
            self.logging.warning('There is a problem executing %s:%s. Reason: %s' % (doc['destination']['name'], doc['destination']['subject'], err))
 
    def processOutput(self,name,data):
        output = []
        verbose = []
        dictionary = {}
        while len(data) != 0:
            line = data.pop(0)
            if str(line) == '~==.==~\n':
                verbose = "\n".join(data)
                break
            else:
                output.append(line)
                try:
                    key_value = line.split(":")
                    dictionary[key_value[0]] = key_value[1].rstrip('\n')
                except:
                    pass
        #Add epoch time
        dictionary["epoch"] = round(time.time())
        #Extend the metrics with the previous ones.
        metrics = self.__cache(name, dictionary)
        return (output, verbose, metrics)
    
    def __cache(self, plugin, dictionary):
        merged_dictionary={}
        cached_dictionary = self.cache.get(plugin, dictionary)
        for value in cached_dictionary:
            merged_dictionary['pre_' + value] = cached_dictionary[value]
        merged_dictionary.update(dictionary)
        self.cache[plugin] = dictionary
        return merged_dictionary


class ExecutePlugin():
    
    def __init__(self):
        self.logging = logging.getLogger(__name__)
        self.process = None
        
    def do(self, name, command=None, parameters=[], timeout=30):
        self.process = None
        command = ("%s %s" % (command, ' '.join(parameters)))
        self.output=None
        def target():
            self.process = Popen(command, shell=True, bufsize=0, stdout=PIPE, stderr=STDOUT, close_fds=True, preexec_fn=os.setsid)
            self.output = self.process.stdout.readlines()
            self.process.stdout.close()
        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)
                
        if thread.is_alive():
            self.logging.warning ( 'Plugin running too long, will terminate it.' )
            try:
                self.process.kill()
            except Exception as err:
                self.logging.warning ( 'Failed to kill plugin %s. Reason: %s' % ( name, err) )
            thread.join()
        else:
            self.process.wait()
            return self.output
    
