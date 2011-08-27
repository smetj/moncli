#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       molog.py
#       
#       Copyright 2010 Jelle Smet <web@smetj.net>
#       
#       This file is part of Monitoring python library.
#       
#           Monitoring python library is free software: you can redistribute it and/or modify
#           it under the terms of the GNU General Public License as published by
#           the Free Software Foundation, either version 3 of the License, or
#           (at your option) any later version.
#       
#           Monitoring python library is distributed in the hope that it will be useful,
#           but WITHOUT ANY WARRANTY; without even the implied warranty of
#           MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#           GNU General Public License for more details.
#       
#           You should have received a copy of the GNU General Public License
#           along with Monitoring python library.  If not, see <http://www.gnu.org/licenses/>.
import MySQLdb,sys,re,time
class connector():
	def __init__(self,host,user,passwd,rsyslogdb='Syslog',mologdb='molog',checkpoint_file=None,logging=None,blockcallback=None):
		'''This class interacts with the MoLog results db.'''
		self.version="0.1"
		self.host=host
		self.user=user
		self.passwd=passwd
		self.rsyslogdb=rsyslogdb
		self.mologdb=mologdb
		self.checkpoint_file=checkpoint_file
		self.last_processed_id=0
		self.logging = logging
		self.loop = blockcallback
		if checkpoint_file != None:
			self.last_processed_id = self.read_checkpoint(file=checkpoint_file)
	def get_db(self):
		while True:
			try:
				connection=MySQLdb.connect(host=self.host,user=self.user,passwd=self.passwd)
				return connection.cursor()
				break
			except Exception as error:
				self.logging.put(['Error','Problem establishing database connection retrying. Reason: %s'%(error)])
			time.sleep(1)
	def read_checkpoint(self,file):
		try:
			checkpoint = open (file,'r')
			offset = checkpoint.readline()
			checkpoint.close()
		except:
			return "0"

		if not re.match('^\d+$',offset):
			return "0"
		else:
			return offset
	def write_checkpoint(self,file,offset):
		checkpoint = open (file,'w')
		checkpoint.write(str(offset))
		checkpoint.close()
	def update(self):
		change=False
		#Query for the last ID in database
		querydb = self.get_db()
		querydb.execute('select max(ID) from Syslog.SystemEvents')
		last_id = querydb.fetchone()[0]
		if last_id == None:
			last_id="0"

		
		#Query all warning records which is between self.last_processed_id and last_id and which are in priorities table
		query = "select SystemEvents.ID,SystemEvents.FromHost,SystemEvents.SysLogTag,SystemEvents.Message from Syslog.SystemEvents where SystemEvents.ID > %s and SystemEvents.ID <= %s and SystemEvents.Priority in (select priority from molog.priority where state = 'warning') order by SystemEvents.ID;"%(self.last_processed_id,last_id)
		querydb.execute(query)

		#For each warning record check if we can ignore it
		for record in querydb.fetchall():
			if self.ignore_record(type='warning',host=record[1],data=[record[2],record[3]]) == True:
				next
			else:
				change=True
				updatedb = self.get_db()
				updatedb.execute ("""insert into molog.results (rsyslog_id,type) values ("%s","%s")"""%(record[0],'warning'))
				updatedb.close()

		#Query all critical records which is between self.last_processed_id and last_id and which are in priorities table
		query ="""select SystemEvents.ID,SystemEvents.FromHost,SystemEvents.SysLogTag,SystemEvents.Message from Syslog.SystemEvents where SystemEvents.ID > %s and SystemEvents.ID <= %s and SystemEvents.Priority in (select priority from molog.priority where state = 'critical') order by SystemEvents.ID;"""%(self.last_processed_id,last_id)
		querydb.execute(query)

		#For each critical record check if we can ignore it
		for record in querydb.fetchall():
			if self.ignore_record(type='critical',host=record[1],data=[record[2],record[3]]) == True:
				next
			else:
				change=True
				updatedb = self.get_db()
				updatedb.execute ("""insert into molog.results (rsyslog_id,type) values ("%s","%s")"""%(record[0],'critical'))
				updatedb.close()
				
		#Remember the last processed id
		self.last_processed_id = last_id
		self.write_checkpoint(file=self.checkpoint_file,offset=last_id)
		
		querydb.close()
		return change
	def ignore_record(self,type=None,host=None,data=None):
		regexes = self.get_regexes(host=host,type=type)
		dataset = " ".join(data)
		for regex in regexes:
			if re.search(regex[1],dataset):
				self.logging.put(['Debug','Ignoring log for host %s with Regex ID %s (%s) -> %s'%(host,regex[0],regex[0],dataset)])
				return True
			else:
				self.logging.put(['Debug','No match for host %s with Regex ID %s (%s) -> %s'%(host,regex[0],regex[1],dataset)])
		return False
	def get_regexes(self,host='.global',type=None):
		regex_query = self.get_db()
		if type == 'warning':
			regex_query.execute("select id,regex from molog.regexes where hostname = %s and warning = 1",(host))
			if int (regex_query.rowcount) == 0:
				regex_query.execute("select id,regex from molog.regexes where hostname = '.global' and warning = 1")
		elif type == 'critical':
			regex_query.execute("select id,regex from molog.regexes where hostname = %s and critical = 1",(host))
			if int (regex_query.rowcount) == 0:
				regex_query.execute("select id,regex from molog.regexes where hostname = '.global' and critical = 1")
		results = regex_query.fetchall()
		regex_query.close()
		return results
	def maintenance(self):
		'''Removes all references which have been marked "deleted" from the molog DB except the lastest warning and critical.
		Returns the amount of rows deleted.'''
		maintenance=self.get_db()
		query = "set @warning=(select max(rsyslog_id) from molog.results where type='warning'); set @critical=(select max(rsyslog_id) from molog.results where type='critical'); delete from molog.results where rsyslog_id > -1 and rsyslog_id != @warning and rsyslog_id != @critical and deleted = 1;"
		maintenance.close()
		return maintenance.execute(query)
	def new_results(self):
		'''Returns a list of hostnames which are not marked as old and marks them.'''
		select_query ="select distinct FromHost from Syslog.SystemEvents join molog.results on molog.results.rsyslog_id = Syslog.SystemEvents.ID where deleted=0 and old=0;"
		mark_query	="update molog.results set results.old=1 where results.old = 0;"
		querydb = self.get_db()
		querydb.execute(select_query)
		select_query_results=querydb.fetchall()
		querydb.execute(mark_query)
		querydb.close()
		return select_query_results[0]
	def get_numbers(self,host):
		'''Returns the amount of critical and warning hits of a host.'''
		querydb = self.get_db()
		query="select FromHost,type,count(*) from Syslog.SystemEvents join molog.results on molog.results.rsyslog_id = Syslog.SystemEvents.ID where deleted=0 and FromHost='%s' group by type;"%(host)
		querydb.execute(query)
		warnings=0
		criticals=0
		for list in querydb.fetchall():
			if list[1]=='critical':
				criticals=list[2]
			elif list[1]=='warning':
				warnings=list[2]
		querydb.close()
		return {'warnings':warnings,'criticals':criticals}
	def get_messages(self,host):
		results={}
		querydb=self.get_db()
		query="select results.id,results.type,ReceivedAt,SyslogTag,Message,NTSeverity,EventSource,EventUser,EventCategory,EventID,EventLogType from Syslog.SystemEvents join molog.results on molog.results.rsyslog_id = Syslog.SystemEvents.ID where molog.results.deleted=0 and Syslog.SystemEvents.FromHost='%s' order by ReceivedAt;"%(host)
		querydb.execute(query)
		for message in querydb.fetchall():
			results[message[0]]={	'type':				message[1],
									'receivedat':		message[2],
									'syslogtag':		message[3],
									'message':			message[4],
									'ntseverity':		message[5],
									'eventsource':		message[6],
									'eventuser':		message[7],
									'eventcategory':	message[8],
									'eventid':			message[9],
									'eventlogtype':		message[10]
									}
		querydb.close()
		return results
	def mark_record_deleted(self,records):
		querydb = self.get_db()
		if str(type(records))=="<type 'list'>":
			for record in records:
				querydb.execute("update molog.results set results.deleted=1 where results.id=%s;"%(record))
		else:
			querydb.execute("update molog.results set results.deleted=1 where results.id=%s;"%(records))
		querydb.close()
	def mark_records_deleted(self,host):
		delete_selection = self.get_db()
		delete_selection.execute ("select molog.results.id from molog.results LEFT JOIN Syslog.SystemEvents ON (molog.results.rsyslog_id = Syslog.SystemEvents.ID) where molog.results.deleted = 0 and Syslog.SystemEvents.FromHost = '%s';"%(host))
		mark_record = self.get_db()

		for record in delete_selection.fetchall():
			query=("update molog set results.deleted = 1 where results.id = %s"%(record[0]))
			mark_record.execute ("update molog.results set results.deleted = 1 where results.id = %s"%(record[0]))
		mark_record.close()
	def size(self):
		querydb = self.get_db()
		querydb.execute("select sum(round(((data_length + index_length - data_free) / 1024 / 1024),2)) as Size from information_schema.tables where table_schema like '%s';"%("Syslog"))
		return str(querydb.fetchall()[0][0])
		querydb.close()
	def index(self):
		'''Returns a dictionary of hostnames with the required results.'''
		results={}
		querydb = self.get_db()
		querydb.execute(query="select SystemEvents.FromHost,type,count(type) from molog.results join Syslog.SystemEvents on Syslog.SystemEvents.ID = molog.results.rsyslog_id where results.deleted=0 group by FromHost,type;")
		for line in querydb.fetchall():
			if not results.has_key(line[0]):
				results[line[0]]={'warnings':'0','criticals':'0','regex':None}
			if line[1]=='warning':
				results[line[0]]['warnings']=line[2]
			elif line[1]=='critical':
				results[line[0]]['criticals']=line[2]
			results[line[0]]['regex']=self.get_regex_type(host=line[0])
		querydb.close()
		return results
	def insert_offset_records(self,now=True):
		'''Checks whether the results table contains at least 2 start records. When now is false then rsylog_id values will be -1 otherwise they will have the
		largest values from the Syslog db.'''
		insert_offset_records=self.get_db()
		warnings=0
		criticals=0
		last_warning_rsyslog_query	='select max(rsyslog_id) from molog.results where results.type="warning";'
		last_critical_rsyslog_query	='select max(rsyslog_id) from molog.results where results.type="critical";'
		
		try:
			insert_offset_records.execute(last_warning_rsyslog_query)
			result=insert_offset_records.execute.fetchall()
			warnings=result[0][0]
			insert_offset_records.execute(last_critical_rsyslog_query)
			criticals=self.insert_offset_records.execute.fetchall()
			criticals=result[0][0]
		except:
			pass
	
		if warnings == 0 or criticals == 0:
			try:
				if now == True:
					if warnings == 0:
						insert_offset_records("insert into molog.results values ( NULL, 'critical', (select max(ID) from Syslog.SystemEvents), '1', '1');")
					if criticals == 0:
						insert_offset_records("insert into molog.results values ( NULL, 'warning', (select max(ID) from Syslog.SystemEvents), '1', '1');")
				else:
					if warnings == 0:
						insert_offset_records("insert into molog.results values ( NULL, 'warning', '-1', '1', '1');")
					if criticals == 0:
						insert_offset_records("insert into molog.results values ( NULL, 'critical', '-1', '1', '1');")
			except:
				pass
		insert_offset_records.close()
	def get_regex(self,host=None):
		get_regex=self.get_db()
		get_regex.execute("select * from molog.regexes where hostname='%s'"%(host))
		results=get_regex.fetchall()
		get_regex.close()
		return results
	def add_regex(self,host,regex,warning=False,critical=False):
		set_regex=self.get_db()
		if warning == False:
			warning = 0
		else:
			warning = 1
		if critical == False:
			critical = 0
		else:
			critical = 1
		set_regex.execute('insert into molog.regexes(hostname,regex,warning,critical) values ("%s","%s","%s","%s");'%(host,regex,warning,critical))
		set_regex.close()
	def update_regex(self,id,regex,warning=False,critical=False):
		update_regex=self.get_db()
		if warning == False:
			warning = 0
		else:
			warning = 1
		if critical == False:
			critical = 0
		else:
			critical = 1
		update_regex.execute("update molog.regexes set regex='%s', warning='%s', critical='%s' where id = '%s'"%(regex,warning,critical,id))
		update_regex.close()
	def del_regex(self,id):
		del_regex=self.get_db()
		del_regex.execute("delete from molog.regexes where id='%s';"%(id))
		del_regex.close()
	def del_regexes(self,host):
		if host != '.global':
			del_regex=self.get_db()
			del_regex.execute("delete from molog.regexes where hostname='%s';"%(host))
			del_regex.close()
	def get_regex_type(self,host):
		results={}
		get_regex_type=self.get_db()
		query="select count(hostname) from molog.regexes where regexes.hostname='%s'"%(host)
		get_regex_type.execute(query)
		if get_regex_type.fetchall()[0][0] == 0:
			get_regex_type.close()
			return '.global'
		else:
			get_regex_type.close()
			return host
