#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       help.py
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

__version__='0.2.4'

def help():
    '''Produces command line help message.'''
    print ('Moncli %s by Jelle Smet <web@smetj.net>' %(__version__))
    print
    print ('''Usage: moncli command [--broker address] [--local_repo directory] [--remote_repo url] [--cache filename] [--pid filename] [--log filename]
    
    Valid commands: 
    
        start   Starts the Moncli daemon in the background.
                    
        stop    Gracefully stops the Moncli daemon running in the background.

        kill    Kills the Moncli daemon running with the pid defined in your config file.
            
        debug   Starts the Moncli daemon in the foreground while showing real time log and debug messages.
                The process can be stopped with ctrl+c which will ends Moncli gracefully.
                A second ctrl+c will kill Moncli.
                
    Parameters: 
        --host          The ipaddress of the message broker Moncli should listen to.
        --vhost         The broker virtual host. Defaults to "/".
        --username      The username used to authenticate against the broker. Defaults to "guest".
        --password      The password used to authenticate against the broker. Defaults to "guest".
        --local_repo    The location of the local plugin repository.
        --remote_repo   The location of the remote plugin repository.
        --cache         The location where the configuration cache is written and read from on startup.
        --pid           The location of the pid file.
        --log           The location of the log file.
        --lib           The library path to include to the search path.
        --rand_window   The value in seconds which is added to the first schedule of a job in order to spread jobs.
                        Default value is 60 seconds.
                        
Moncli is distributed under the Terms of the GNU General Public License Version 3. (http://www.gnu.org/licenses/gpl-3.0.html)

For more information please visit http://www.smetj.net/moncli/
''')
