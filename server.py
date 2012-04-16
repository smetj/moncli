#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       untitled.py
#       
#       Copyright 2012 Jelle <jelle@indigo>
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

import sys
sys.path.append('/opt/untitled/lib/modules')

import wishbone
import moncli

from gevent.socket import getfqdn


if __name__ == '__main__':
    
    wb = wishbone.Wishbone()
    wb.registerBroker( host='sandbox', vhost='/', username='guest', password='guest', consume_queue=getfqdn() )
    wb.registerUDPServer ( port='9001' )
    
    wb.registerBlock ( 'wishbone', 'JSONValidator', 'validateBrokerData', schema='/opt/untitled/lib/schema/broker' )
    wb.registerBlock ( 'wishbone', 'JSONValidator', 'validateUDPData', schema='/opt/untitled/lib/schema/udp' )

    wb.registerBlock ( 'moncli', 'Scheduler', 'scheduler', file='/opt/untitled/lib/cache/scheduler', delay=0 )
    wb.registerBlock ( 'moncli', 'Executor', 'executor', base='/opt/untitled/lib/repository' )
    wb.registerBlock ( 'moncli', 'Collector', 'collector' )

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
    
    #OUTPUT
    #Collector --> Broker(exitPoint)
    wb.connect (wb.collector.outbox, wb.broker.outbox)
    
    #Start your engines
    try:
        wb.start()
    except KeyboardInterrupt:
        wb.stop()
        
