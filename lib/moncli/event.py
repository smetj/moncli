#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       event.py
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

from jsonschema import Validator
from uuid import uuid4
from time import strftime, localtime
from tools import Calculator
import logging

class Request():
    def __init__(self,doc):
        self.logging = logging.getLogger(__name__)
        self.calc = Calculator()
        self.__load(doc)
        self.answer = self.__initReport(doc)
    def __load(self,doc):
        self.__dict__.update(doc)        
    @staticmethod
    def validate(data):
        checker = Validator()
        document_schema = {
            "type" : "object",
            "additionalProperties": False,
            "properties" : {
                "source" : {
                    "type" : "object",
                    "required" : True,
                    "additionalProperties": False,
                    "properties" : {
                        "name" : {"type" : "string", "required" : True }
                    }
                },
                "destination" : {
                    "type" : "object",
                    "required" : True,
                    "additionalProperties": False,
                    "properties" : {
                        "name" : {"type" : "string", "required" : True },
                        "subject" : {"type" : "string", "required" : True }
                    }
                },
                "report" : {
                    "type" : "object",
                    "required" : True,                    
                    "additionalProperties": False,
                    "properties" : {
                        "message" : {"type" : "string", "required" : True },
                    }
                },
                "request" : {
                    "type" : "object",
                    "required" : True,                    
                    "additionalProperties": False,
                    "properties" : {
                        "uuid" : {"type" : "string", "required" : True },
                        "time" : {"type" : "string", "required" : True },
                        "day_of_year" : {"type" : "number", "required" : True },
                        "day_of_week" : {"type" : "number", "required" : True },
                        "week_of_year" : {"type" : "number", "required" : True },
                        "month" : {"type" : "number", "required" : True },
                        "year" : {"type" : "number", "required" : True },
                        "day" : {"type" : "number", "required" : True },
                        "cycle" : {"type" : "number", "required" : True },
                    }
                },
                "plugin" : {
                    "type" : "object",
                    "required" : True,                    
                    "additionalProperties": False,
                    "properties" : {
                        "name" : {"type" : "string", "required" : True },
                        "hash" : {"type" : "string", "required" : True },
                        "timeout" : {"type" : "number", "required" : True },
                        "parameters" : {"type" : "string", "required" : True }
                    }
                },
                "evaluators" : {
                    "type" : "object",
                    "required" : True
                },
                "tags" : {
                    "type" : "array",
                    "required" : True
                }
            }
        }
        evaluator_schema = {
            "type" : "object",
            "additionalProperties": False,
            "properties" : {
                "evaluator" : {"type" : "string", "required" : True },
                "metric" : {"type" : "string", "required" : True },
                "thresholds" : {"type" : "object", "required" : True }
            }
        }
        threshold_schema = {
                "type" : "string"
        }
        checker.validate(data,document_schema)
        for evaluator in data['evaluators']:
            checker.validate(data['evaluators'][evaluator],evaluator_schema)
            for threshold in data['evaluators'][evaluator]['thresholds']:
                checker.validate(data['evaluators'][evaluator]['thresholds'][threshold],threshold_schema)
    def generateReport(self):
        pass
    def __initReport(self,doc):
        return {
           "source":{
              "uuid":doc['request']['uuid'],
           },
           "destination":{
              "name":doc['destination']['name'],
              "subject":doc['destination']['subject'],
           },
           "report":{
              "uuid":str(uuid4()),
              "message":None,
              "time":strftime("%Y-%m-%dT%H:%M:%S%z", localtime()),
              "day_of_year":strftime("%j"),
              "day_of_week":strftime("%w"),
              "week_of_year":strftime("%W"),
              "month":strftime("%m"),
              "year":strftime("%Y"),
              "day":strftime("%d")
           },
           "plugin":{
              "name":doc['plugin']['name'],
              "verbose":None,
              "metrics":None,
              "raw":None
           },
           "evaluators":{
           },
           "tags":doc['tags']
        }
    def calculate(self):
        for evaluator in self.evaluators:
            (value,status)  = self.calc.do(   output=self.answer['plugin']['raw'],
                                    dictionary=self.answer['plugin']['metrics'],
                                    evaluator=self.evaluators[evaluator]['evaluator'],
                                    thresholds=self.evaluators[evaluator]['thresholds'])

            self.answer["evaluators"].update({ evaluator : { "status" : status, "metric" : self.evaluators[evaluator]['metric'], "value" : value } })
        
        self.answer['report']['message']=self.buildMessage(evaluators=self.answer['evaluators'],message=self.report['message'])
    def buildMessage(self,evaluators,message):
        for evaluator in evaluators:
            message=message.replace('#'+str(evaluator),'(%s) %s'%(evaluators[evaluator]['status'],evaluators[evaluator]['value']))
        return message
