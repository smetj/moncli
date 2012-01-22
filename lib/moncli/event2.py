#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       event2.py
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



class ReportRequest():
    def __init__(self):
        pass
    def validate(self,object):
        @staticmethod
        checker = Validator()
        document_schema = {
            "type" : "object",
            "additionalProperties": False,
            "properties" : {
                "source" : {
                    "type" : "object",
                    "additionalProperties": False,
                    "properties" : {
                        "name" : {"type" : "string" }
                    }
                },
                "destination" : {
                    "type" : "object",
                    "additionalProperties": False,
                    "properties" : {
                        "name" : {"type" : "string" },
                        "subject" : {"type" : "string" }
                    }
                },
                "report" : {
                    "type" : "object",
                    "additionalProperties": False,
                    "properties" : {
                        "message" : {"type" : "string" },
                    }
                },
                "request" : {
                    "type" : "object",
                    "additionalProperties": False,
                    "properties" : {
                        "uuid" : {"type" : "string" },
                        "time" : {"type" : "string" },
                        "day_of_year" : {"type" : "number" },
                        "day_of_week" : {"type" : "number" },
                        "week_of_year" : {"type" : "number" },
                        "month" : {"type" : "number" },
                        "year" : {"type" : "number" },
                        "day" : {"type" : "number" },
                        "cycle" : {"type" : "number" },
                    }
                },
                "plugin" : {
                    "type" : "object",
                    "additionalProperties": False,
                    "properties" : {
                        "name" : {"type" : "string" },
                        "hash" : {"type" : "string" },
                        "timeout" : {"type" : "number" },
                        "parameters" : {"type" : "string" }
                    }
                },
                "evaluators" : {
                    "type" : "object"
                },
                "tags" : {
                    "type" : "array",
                }
            }
        }
        evaluator_schema = {
            "type" : "object",
            "additionalProperties": False,
            "properties" : {
                "evaluator" : {"type" : "string" },
                "metric" : {"type" : "string" },
                "thresholds" : {"type" : "object" }
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
