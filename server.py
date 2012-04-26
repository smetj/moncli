#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       server.py
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

from sys import path;path.append('/opt/moncli/lib/modules')
from gevent.socket import getfqdn
from wishbone import wishbone
import moncli


if __name__ == '__main__':
    
    wb = wishbone.Wishbone()
    
    wb.registerModule ( ('wishbone.io_modules', 'Broker', 'broker'), host='sandbox', vhost='/', username='guest', password='guest', consume_queue=getfqdn() )
    wb.registerModule ( ('wishbone.io_modules', 'UDPServer', 'udp_server'), port='9001' )  
    
    wb.registerModule ( ('wishbone.modules', 'JSONValidator', 'validateBrokerData'), schema='/opt/moncli/lib/schema/broker', convert=True )
    wb.registerModule ( ('wishbone.modules', 'JSONValidator', 'validateUDPData'), schema='/opt/moncli/lib/schema/udp', convert=True )
    wb.registerModule ( ('wishbone.modules', 'Compressor', 'compressor') )

    wb.registerModule ( ('moncli', 'Scheduler', 'scheduler'), file='/opt/moncli/lib/cache/scheduler', delay=0 )
    wb.registerModule ( ('moncli', 'Executor', 'executor'), base='/opt/moncli/lib/repository' )
    wb.registerModule ( ('moncli', 'Collector', 'collector') )

    #INPUT
    #Broker(entryPoint) --> Validator
    wb.connect (wb.broker.inbox, wb.validateBrokerData.inbox)
    
    #Validator --> Scheduler
    wb.connect (wb.validateBrokerData.outbox, wb.scheduler.inbox)
        
    #Scheduler --> Executor
    wb.connect (wb.scheduler.validate, wb.validateBrokerData.inbox)
    wb.connect (wb.scheduler.outbox, wb.executor.inbox)
    
    #Executor --> Collector
    wb.connect (wb.executor.outbox, wb.collector.inbox)
      
    #INPUT
    #From UDP input to Broker output
    #UDPserver(entrypoint) --> Validator
    wb.connect (wb.udp_server.inbox, wb.validateUDPData.inbox)
    
    #Validator --> Collector
    wb.connect (wb.validateUDPData.outbox, wb.collector.inbox)
    
    #Collector -->  Compressor
    wb.connect (wb.collector.outbox, wb.compressor.inbox)
    
    #OUTPUT
    #compressor --> Broker(exitPoint)
    wb.connect (wb.compressor.outbox, wb.broker.outbox)
    
    #Start your engines
    try:
        wb.start()
    except KeyboardInterrupt:
        wb.stop()
        
