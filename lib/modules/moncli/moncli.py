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
from wishbone.wishbone import PrimitiveActor
from gevent import monkey; monkey.patch_all()

class Scheduler(PrimitiveActor):
    '''A scheduler schedules incoming requests, loads and saves scheduled jobs to disk for later retrieval.'''

    def __init__(self, name, block, *args, **kwargs):
        PrimitiveActor.__init__(self, name, block)
        self.schedule_list={}
        self.docs={}
        self.file = kwargs.get('file','/tmp/blah')
        self.delay = kwargs.get('delay',60)
        self.validate = Queue(None)
        self.load()
   
    def consume(self, doc):
        self.schedule(doc)
        
    def schedule(self, doc):
        if self.schedule_list.has_key(doc["request"]["subject"]):
            self.schedule_list[doc["request"]["subject"]].kill()
            self.schedule_list[doc["request"]["subject"]].join()
            del(self.docs[doc["request"]["subject"]])
        if doc["plugin"]["cycle"] == "0":
            self.outbox.put(doc)
        else:
            self.docs[doc["request"]["subject"]]=json.dumps(doc)
            self.schedule_list[doc["request"]["subject"]]=spawn(self.runner,doc)

    def runner(self,doc):
        wait = randint(0, self.delay)
        self.logging.info( 'Generate request %s with a delay of %s seconds.' % (doc["request"]["subject"], wait))
        if doc["plugin"]["cycle"] != 0:
            sleep(float(wait))
            while self.block() == True:
                self.outbox.put(doc)
                sleep (float(doc["plugin"]["cycle"]))
        else:
            self.outbox.put(doc)
    
    def shutdown(self):
        self.save()
        self.logging.info('Shutdown')
    
    def save(self):
        try:
            output = open(self.file, 'wb')
            dump(self.docs, output)
            output.close()
            self.logging.info('Config saved.')
        except Exception as err:
            self.logging.warn('There was a problem saving the config. Reason: %s.' % (err))
    
    def load(self):
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
    '''A executes incoming requests.'''

    def __init__(self, name, block, *args, **kwargs):
        PrimitiveActor.__init__(self, name, block)
        self.base = kwargs.get('base','./')
      
    def consume(self,doc):
        self.logging.info('Executing plugin %s' % doc['plugin']['name'])
        spawn(self.do, doc)

    def do(self, doc):
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
                self.outbox.put(doc)     
    
    def exe(self, command):
        process = gevent_subprocess.Popen(command, shell=True, stdout=gevent_subprocess.PIPE, stderr=gevent_subprocess.PIPE)
        output=[]
        for line in process.stdout.readlines():
            output.append(line.strip())
            
        #output = process.stdout.readlines()
        process.stdout.close()
        process.stderr.close()
        return output
             
    def verifyHash(self, fullpath):
        plugin = open(fullpath,'r')
        plugin_hash = md5()
        plugin_hash.update((''.join(plugin.readlines())))
        plugin.close()
        
        if path.basename(fullpath) != plugin_hash.hexdigest():
            raise Exception ( 'Plugin filename does not match its hash value.' )
            self.logging.warning ( 'Plugin filename %s does not match its hash value %s.'%(file,plugin_hash.hexdigest() ) )

    def shutdown(self):
        self.logging.info('Shutdown')


class Collector(PrimitiveActor):
    
    def __init__(self, name, block, *args, **kwargs):
        PrimitiveActor.__init__(self, name, block)
      
    def consume(self,doc):
        doc = deepcopy(doc)
        exchange = doc['destination']['exchange']
        key = doc['destination']['key']
        del(doc['destination'])
        here_now = localtime()
        iso8601 = strftime("%Y-%m-%dT%H:%M:%S",here_now)
        iso8601 += strftime("%z")
        doc['request']['uuid']=str(uuid4())
        doc['request']['time']=iso8601
        self.outbox.put((exchange, key, json.dumps(doc)))
       
    def shutdown(self):
        self.logging.info('Shutdown')
