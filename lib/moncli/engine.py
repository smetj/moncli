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
from urllib import urlretrieve
from apscheduler import scheduler
from amqplib import client_0_8 as amqp
from socket import getfqdn
from threading import Lock
import Queue
from random import randint
from datetime import datetime, timedelta
from subprocess import Popen, STDOUT, PIPE
from tools import PluginManager
from moncli.event import Request
from signal import SIGTERM
import threading
import pickle
import json
import os
import time
import logging
import sys
#import stopwatch



class Broker(threading.Thread):
    
    def __init__(self,host='localhost',vhost='/',username='guest',password='guest',exchange='',incoming_q_name=getfqdn(),outgoing_q_name='moncli_reports',scheduler_callback=None,block=None):
        threading.Thread.__init__(self)
        self.logging = logging.getLogger(__name__)
        self.host=host
        self.vhost=vhost
        self.username=username
        self.password=password
        self.exchange=exchange
        self.incoming_q_name=incoming_q_name
        self.outgoing_q_name=outgoing_q_name
        self.outgoing_queue=Queue.Queue(0)
        self.scheduler_callback=scheduler_callback
        self.block=block
        self.connected=False
        self.daemon=True

    def __setup(self):
        self.conn = amqp.Connection(host="%s:5672"%(self.host), userid=self.username,password=self.password, virtual_host=self.vhost, insist=False)
        self.incoming = self.conn.channel()
        self.outgoing = self.conn.channel()
        self.incoming.basic_consume(queue=self.incoming_q_name, callback=self.consume)
        self.logging.info('Connected to broker')
    
    def submitBroker(self):
        while self.block() == True:
            while self.connected == True:
                while self.outgoing_queue.qsize() > 0:
                    try:
                        self.logging.info('Submitting data to broker')
                        self.produce(self.outgoing_queue.get())
                    except:
                        break
                time.sleep(0.1)
            time.sleep(1)
                                
    def run(self):
        night=0.5
        self.startProduceThread()
        while self.block() == True:
            try:
                if night < 512:
                    night *=2
                self.__setup()
                self.connected=True
                night=0.5
                self.incoming.wait()
            except Exception as err:
                self.connected=False
                self.logging.warning('Connection to broker lost. Reason: %s. Try again in %s seconds.' % (err,night) )
                time.sleep(night)
            #self.incoming.close()
            #self.outgoing.close()
            #self.conn.close()
        self.produce.join()
    def startProduceThread(self):
        self.produce_thread = threading.Thread(target=self.submitBroker)
        self.produce_thread.start()
        
    def consume(self,doc):
        try:
            self.scheduler_callback(json.loads(doc.body))
            self.incoming.basic_ack(doc.delivery_tag)
        except:
            print "kakakakakakan"
        
    def produce(self,data):
        if self.connected == True:
            msg = amqp.Message(str(data))
            msg.properties["delivery_mode"] = 2
            self.outgoing.basic_publish(msg,exchange=self.exchange,routing_key=self.outgoing_q_name)
        else:
            raise Exception('Not Connected to broker')
            
            
class ReportRequestExecutor():
    '''Don't share this class over multiple threads/processes.'''

    def __init__(self, local_repo, remote_repo, submitBroker):
        self.logging = logging.getLogger(__name__)
        self.pluginManager = PluginManager(local_repository=local_repo,
                                remote_repository=remote_repo)
        self.executePlugin = ExecutePlugin()
        self.submitBroker = submitBroker
        self.cache = {}

    def do(self,doc):
        try:
            #t = stopwatch.Timer()
            self.logging.info('Executing a request with destination %s:%s' % (doc['destination']['name'], doc['destination']['subject']))
            request = Request(doc=doc)
            command = self.pluginManager.getExecutable(command=request.plugin['name'], hash=request.plugin['hash'])
            output = self.executePlugin.do(request.plugin['name'], command, request.plugin['parameters'], request.plugin['timeout'])
            (raw, verbose, metrics) = self.processOutput(request.plugin['name'],output)
            request.insertPluginOutput(raw, verbose, metrics)            
            self.submitBroker.put(request.answer)
            #t.stop()
            #self.logging.debug('Job %s:%s took %s seconds.' % (doc['destination']['name'],doc['destination']['subject'],t.elapsed))
        except Exception as err:
            self.logging.warning('There is a problem executing %s:%s. Reason: %s' % (doc['destination']['name'], doc['destination']['subject'], err))
            
    def processOutput(self,name,data):
        output = []
        verbose = []
        dictionary = {}
        while len(data) != 0:
            line = data.pop(0)
            if str(line) == '~==.==~\n':
                for i,v in enumerate(data):
                    data[i] = v.rstrip('\n')
                verbose = data
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


class JobScheduler():

    def __init__(self, cache_file, local_repo, remote_repo):
        self.logging = logging.getLogger(__name__)
        self.sched = scheduler.Scheduler()
        self.submitBroker = None
        self.request = {}
        self.cache_file = cache_file
        self.local_repo = local_repo
        self.remote_repo = remote_repo
        self.do_lock = Lock()
        self.sched.start()

    def do(self, doc):
        name = self.__name(doc)
        if self.request.has_key(name):
            self.__unschedule(name=name, object=self.request[name]['scheduler'])
        if doc['request']['cycle'] == 0:
            self.logging.debug('Executed imediately job %s' % (name))
            #ToDo (smetj): take broker communication out of ReportRequestExecutor.  It doesn't belong there.
            job = ReportRequestExecutor(local_repo=self.local_repo, remote_repo=self.remote_repo)
            job.do(doc=doc)
        else:
            self.__schedule(doc=doc)
        self.__save()

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
                                                        coalesce=True,
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
            self.process.wait()
        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)
                
        if thread.is_alive():
            self.logging.debug ( 'Plugin %s is running too long, will terminate it.' % (name) )
            os.killpg(self.process.pid,SIGTERM)
            self.logging.debug ('Waiting for thread %s to exit.' % (thread.getName()))
            thread.join()
            self.logging.debug ('Thread %s exit.' % (thread.getName()))
            raise Exception( 'Plugin %s running too long. Terminated.' % (name) )
        else:
            return self.output
    

