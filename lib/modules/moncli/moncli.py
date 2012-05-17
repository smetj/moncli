#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       engine.py
#       
#       Copyright 2012 Jelle Smet development@smetj.net
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

import logging
import json
from copy import deepcopy
from os import path
from uuid import uuid4
from time import strftime, localtime
from random import randint
from pickle import dump, load
from hashlib import md5
from random import randint
from gevent import sleep, spawn
from gevent.queue import Queue
from gevent_subprocess import gevent_subprocess
from wishbone.toolkit import PrimitiveActor
from gevent import monkey; monkey.patch_all()

class Scheduler(PrimitiveActor):
    '''A custom WishBone module resubmits messages back to the validate queue at the interval defined in message['data']['plugin']['cycle'].
    
    The Scheduler can save and load the schedulers state from disk.
    
    This module accepts 2 parameters:
        file:   The location of the scheduler state file.
        delay:  The maximum value for choosing a random initial delay in order to spread multiple checks.'''

    def __init__(self, name, *args, **kwargs):
        PrimitiveActor.__init__(self, name)
        self.name = name
        self.schedule_list={}
        self.docs={}
        self.file = kwargs.get('file','/tmp/blah')
        self.delay = kwargs.get('delay',60)
        self.validate = Queue(None)
        self.load()
   
    def consume(self, message):
        '''Executed for each incoming message.'''
        
        self.schedule(message['data'])
        
    def schedule(self, doc):
        '''Manages the scheduling schema for each incoming message.'''
        
        if self.schedule_list.has_key(doc["request"]["subject"]):
            self.schedule_list[doc["request"]["subject"]].kill()
            self.schedule_list[doc["request"]["subject"]].join()
            del(self.docs[doc["request"]["subject"]])
        if doc["plugin"]["cycle"] == "0":
            self.sendData(doc)
        else:
            self.docs[doc["request"]["subject"]]=json.dumps(doc)
            self.schedule_list[doc["request"]["subject"]]=spawn(self.runner,doc)

    def runner(self,doc):
        '''Each scheduled message is a new backgrounded GreenThread with an interval sleep.  This function writes the the outbox queue.'''
        
        wait = randint(0, self.delay)
        self.logging.info( 'Generate request %s with a delay of %s seconds.' % (doc["request"]["subject"], wait))
        if doc["plugin"]["cycle"] != 0:
            sleep(float(wait))
            while self.block() == True:
                self.sendRaw(doc)
                sleep (float(doc["plugin"]["cycle"]))
        else:
            self.sendData(doc)
    
    def shutdown(self):
        '''When called during shutdown will trigger the save() function.'''
        self.save()
        self.logging.info('Shutdown')
    
    def save(self):
        '''Actually saves the schedule to disk.'''
        
        try:
            output = open(self.file, 'wb')
            dump(self.docs, output)
            output.close()
            self.logging.info('Config saved.')
        except Exception as err:
            self.logging.warn('There was a problem saving the config. Reason: %s.' % (err))
    
    def load(self):
        '''Loads the schedule from disk.'''
        try:
            input = open(self.file, 'r')
            data = load(input)
            input.close()
            for doc in data:
                self.validate.put(data[doc])
            self.logging.info('Config loaded.')
        except Exception as err:
            self.logging.info('There was a problem loading the config. Reason: %s.' % (err))


class Executor(PrimitiveActor):
    '''A custom WishBone module which executes a shell command and completes the message['data'] structure with its results.
    
    The Executor expects message["data"]["plugin] to contain:
    
              "name":"disks",
              "hash":"38ff93ae8cf2d108e4b53b158ec7c914",
              "timeout":60,
              "cycle":1,
              "parameters":[

              ]
    
    name:       The name of the directory which contains the actual plugin.
    hash:       The actual filename of the plugin to execute.  The full path of the plugin would be /base/name/hash
    timeout:    The maximum amount of seconds a plugin is allowed to run before its killed.
    cycle:      The amount in seconds that the Scheduler has to repeat this message.
    parameters: A list of all space separated parameters used to executed the plugin.
    
    This module accepts 1 parameter:
    
        base:   The location of the directory containing the plugins to execute.

    '''

    def __init__(self, name, *args, **kwargs):
        PrimitiveActor.__init__(self, name)
        self.base = kwargs.get('base','./')
      
    def consume(self,message):
        '''Executed for each incoming message.'''
        
        self.logging.info('Executing plugin %s' % message['data']['plugin']['name'])
        spawn(self.do, message)

    def do(self, message):
        'Actually executes the plugin.'''
        doc = message['data']
        command = ("%s/%s/%s %s" % (self.base,doc['plugin']['name'], doc['plugin']['hash'], ' '.join(doc['plugin']['parameters'])))
        try:
            self.verifyHash("%s/%s/%s" % (self.base,doc['plugin']['name'], doc['plugin']['hash']))
        except Exception as err:
            self.logging.warn('Plugin %s does not have a correct filename/hash combination. Reason: %s' % (doc['plugin']['name'], err))
        else:
            current = spawn(self.exe, command)
            current.join(doc['plugin']['timeout'])
            if not current.ready():
                self.logging.warn('Plugin %s is running too long. Will kill it.' % (command))
                current.kill()
            else:
                doc['data']={'raw':current.value}
                self.sendData(message)
    
    def exe(self, command):
        '''Is executed by do() into a background GreenThread and handles all the subprocess communication.'''
        
        process = gevent_subprocess.Popen(command, shell=True, stdout=gevent_subprocess.PIPE, stderr=gevent_subprocess.PIPE)
        output=[]
        for line in process.stdout.readlines():
            output.append(line.strip())
            
        #output = process.stdout.readlines()
        process.stdout.close()
        process.stderr.close()
        return output
             
    def verifyHash(self, fullpath):
        '''Checks the actual hash of the file against its filename.'''
        
        plugin = open(fullpath,'r')
        plugin_hash = md5()
        plugin_hash.update((''.join(plugin.readlines())))
        plugin.close()
        
        if path.basename(fullpath) != plugin_hash.hexdigest():
            raise Exception ( 'Plugin filename does not match its hash value.' )
            self.logging.warning ( 'Plugin filename %s does not match its hash value %s.'%(file,plugin_hash.hexdigest() ) )


class Collector(PrimitiveActor):
    '''A custom WishBone module which extends the incoming message with additional data.'''
        
    def __init__(self, name, *args, **kwargs):
        PrimitiveActor.__init__(self, name)
      
    def consume(self,message):
        '''Executed for each incoming message.'''
        
        message['header']['broker_exchange'] = message['data']['destination']['exchange']
        message['header']['broker_key'] = message['data']['destination']['key']
        del(message['data']['destination'])
        here_now = localtime()
        iso8601 = strftime("%Y-%m-%dT%H:%M:%S",here_now)
        iso8601 += strftime("%z")
        message['data']['request']['uuid']=str(uuid4())
        message['data']['request']['time']=iso8601
        self.sendData(message)
