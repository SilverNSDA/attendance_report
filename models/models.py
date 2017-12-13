# -*- coding: utf-8 -*-

from odoo import models, fields, api

from datetime import datetime, date, timedelta, time
from dateutil import tz, rrule
import pytz
import calendar
import copy

# class AttendanceTable(models.Model):
class AttendanceTable(models.TransientModel):
	_name = 'attendance.table.report'

	@api.model
	def get_html(self,domain,*args, **kwargs):
		context_lang = self.env.context.get('lang','en_US')
		res_lang = self.env['res.lang'].search([('code','=',context_lang)])
		context_date_fmt = "%m/%d/%Y"
		if res_lang:
			context_date_fmt = res_lang.date_format

		date_fmt = '%Y-%m-%d'
		filter_date_from = kwargs['filters']['date_from']
		filter_date_to = kwargs['filters']['date_to']
		date_from = datetime.strptime(filter_date_from,date_fmt).date()
		date_to = datetime.strptime(filter_date_to,date_fmt).date()

		employees = self.env['hr.employee'].search(domain)
		departments = employees.mapped('department_id')
		# print '\n ---> departments',departments
		# atd_report_data = self.env['attendance.table.report'].get_employee_attendance_date_report(departments.mapped('member_ids.id'),date_from,date_to)
		atd_report_data = self.get_employee_attendance_date_report(departments.mapped('member_ids.id'),date_from,date_to)
		
		atd_report_data.update({
			'departments': departments,
			'employees': employees,
			'dates': self._get_day_range(date_from,date_to),
			"date_from": date_from.strftime(context_date_fmt),
			"date_to": date_to.strftime(context_date_fmt),
		})
		html = self.env['report'].render('jy_attendance_report.report_attendance', atd_report_data)
		report_context = {
			"user_date_format":context_date_fmt,
			"new_leave":{
				"min_time":datetime.min.time().strftime("%H:%M:%S"),
				"max_time":datetime.max.time().strftime("%H:%M:%S"),
			}
		}
		return {
			"html":html,
			"report_context": report_context
		}

	@api.model
	def _get_day_range(self,date_from,date_to):
		# TODO: update holiday status
		dt = date_to - date_from
		res = []
		for i in range(dt.days + 1):
			di = date_from + timedelta(days=i)
			res.append({
				'simple': di.strftime('%d/%m'),
				'date': di.strftime('%Y-%m-%d'),
				# 'year': di.year,
				# 'month': di.month,
				# 'day': di.day,
				'weekday': di.strftime('%a'),
				# 'weekday_num': di.weekday(),
				'is_weekend': di.weekday() == 6 ,
				# 'is_holiday':False,
			})
		# print '\n Date range',res
		return res

	@api.model
	def _get_holidays(self,country_ids,date_from,date_to):
		date_fmt = '%Y-%m-%d'
		hlines = self.env['hr.holidays.public.line'].search([('year_id.country_id','in',country_ids),('date','>=',date_from.strftime(date_fmt)),('date','<=',date_to.strftime(date_fmt))])
		res = {}
		for l in hlines:
			cid = l.year_id.country_id.id
			if cid not in res:
				res[cid] = {}
			res[cid][l.date] = {
				'id':l.year_id.id,
				'name': l.year_id.display_name,
				'line_name': l.name,
				'line_id':l.id,
			}
		return res

	@api.model
	def get_employee_attendance_date_report(self,ids,date_from,date_to):
		print '\n\n ==> get_employee_attendance_date_report',ids,date_from,date_to
		# Generate blank report
		res_atds = {}
		res_attrs = {} # Employee attributes 
		res_leaves = {} # Leaves info
		
		date_fmt = '%Y-%m-%d'
		datetime_fmt = "%Y-%m-%d %H:%M:%S"
		dt = date_to - date_from
		dates_template = {}
		for i in range(dt.days + 1):
			di = date_from + timedelta(days=i)
			
			dates_template[di.strftime(date_fmt)] = {
				'weekday':di.weekday(),
				'worked_hours':0,
				'ot_worked_hours':0,
				'type':'work',
				'code':'', # to show on Date cell, ex: CP, KP, ...
				'bg_class':'', # background class,
				'full_hours':8.0,
				'missing_hours':0,  # full_hours - total worked_hours
				'leave':False,
				'leave_ids':[],
				'waiting_approved_leave_count':0,
				'holidays':False,
			}
		for eid in ids:
			res_atds[eid] = copy.deepcopy(dates_template)
			res_attrs[eid] = {
				'worked_hours':0,
				'ot_worked_hours':0,
				'full_working':True,
				'approved_leave_ids':[], # list of approved leave ids
				'approved_leave_count':0, # count approved leave days
				'no_approved_leave_count':0, # count un-approved leave days
			}
		# print '\n ------> RES Blank template',res_atds
		time_from = datetime.combine(date_from, datetime.min.time()).strftime(datetime_fmt)
		time_to = datetime.combine(date_to, datetime.max.time()).strftime(datetime_fmt)
		atds = self.env['hr.attendance'].search([('employee_id','in',ids),('check_in','>=',time_from),('check_out','<=',time_to)])
		# print '\n --> attendances',atds
		if len(atds):
			for atd in atds:
				res_atds[atd.employee_id.id][atd.check_in_date]['worked_hours'] += atd.worked1_hours
				res_atds[atd.employee_id.id][atd.check_in_date]['ot_worked_hours'] += atd.worked2_hours
				res_attrs[atd.employee_id.id]['worked_hours'] += atd.worked1_hours
				res_attrs[atd.employee_id.id]['ot_worked_hours'] += atd.worked2_hours
				print '\n 1 missing hours',res_atds[atd.employee_id.id][atd.check_in_date]['missing_hours']
		country_ids = self.env['hr.employee'].search([('id','in',ids)]).mapped('working_country_id.id')
		# print '\n\n ===> Employee working country_ids',country_ids
		HOLIDAYS = self._get_holidays(country_ids,date_from,date_to)
		# print 'HOLIDAYS',HOLIDAYS
		# Update mode and message
		for eid in ids:
			# Get employee calendar
			employee = self.env['hr.employee'].browse(eid)
			ecal = employee.calendar_id
			cid = employee.working_country_id.id if employee.working_country_id else False
			for d,atd_data in res_atds[eid].iteritems():
				# Check if d is weekend
				WEEK_DAYS = ecal.attendance_ids.mapped(lambda catd: int(catd.dayofweek))
				WEEK_DAYS = list(set(WEEK_DAYS))

				# Get min time and max time in DI date to get full working hours
				di = datetime.strptime(d,date_fmt)
				di_time0 = datetime.combine(di, datetime.min.time())
				di_time1 = datetime.combine(di, datetime.max.time())
				full_hours = ecal.get_working_hours_of_date(start_dt=di_time0,end_dt=di_time1)
				# Update full working hours
				res_atds[eid][d].update({
					'full_hours':full_hours
				})
				if cid and (cid in HOLIDAYS) and (d in HOLIDAYS[cid]):
					res_atds[eid][d].update({
						'type':'holidays',
						'bg_class':'info',
						'holidays':HOLIDAYS[cid][d],
					})
				else:
					if res_atds[eid][d]['worked_hours'] == 0:
						# Exclude weekend
						if res_atds[eid][d]['weekday'] in WEEK_DAYS:
							res_atds[eid][d].update({
								'type':'absence',
								# 'code': 'NO_LEAVE',
								# 'message': '',
								'bg_class': 'danger'
							})
					elif res_atds[eid][d]['worked_hours'] < full_hours:
						res_atds[eid][d].update({
							'bg_class': 'warning'
						})

		# Consider Leaves
		time_from_str = datetime.combine(date_from, datetime.min.time()).strftime(datetime_fmt)
		time_to_str = datetime.combine(date_to, datetime.max.time()).strftime(datetime_fmt)
		
		# all_leaves = self.env['hr.holidays'].search([('employee_id','in',ids),('type','=','remove'),('state','=','validate')])
		# all_leaves = self.env['hr.holidays'].search([('employee_id','in',ids),('type','=','remove'),('state','=','validate'),('date_from','<=',time_to_str),('date_to','>=',time_from_str)])
		all_leaves = self.env['hr.holidays'].search([('employee_id','in',ids),('type','=','remove'),('date_from','<=',time_to_str),('date_to','>=',time_from_str)])
		# print '\n ===> LEAVES',all_leaves
		for lv in all_leaves:
			# Get leave date object
			leave_from = datetime.strptime(lv.date_from,datetime_fmt).replace(hour=0,minute=0).date()
			leave_to = datetime.strptime(lv.date_to,datetime_fmt).replace(hour=0,minute=0).date()
			leave_dt = leave_to - leave_from
			for i in range(leave_dt.days + 1):
				li = leave_from + timedelta(days=i)
				li_date = li.strftime(date_fmt)
				eid = lv.employee_id.id
				if li_date in res_atds[eid]:
					# Collect all leaves data
					res_leaves[lv.id] = {
						'id':lv.id,
						'name':lv.name,
						'state':lv.state,
						'display_name':lv.display_name,
						'date_from': self._convert_utc_to_timezone(lv.date_from,"%Y-%m-%d %H:%M"),
						'date_to': self._convert_utc_to_timezone(lv.date_to,"%Y-%m-%d %H:%M"),
						'duration': lv.number_of_days_temp,
						'leave_type':lv.holiday_status_id.name,
					}

					res_atds[eid][li_date].update({
						'type':'leave',
						# 'code':'LEAVE',
						# 'leave':lv.id,
						'leave':True,
						# 'bg_class':'success',
					})
					res_atds[eid][li_date]['leave_ids'].append(lv.id)
					# Update number of leave count
					if lv.state == 'validate':
						if lv.id not in res_attrs[eid]['approved_leave_ids']:
							res_attrs[eid]['approved_leave_ids'].append(lv.id)
					else:
						res_atds[eid][li_date]['waiting_approved_leave_count'] += 1
					# Update Attributes
					res_attrs[eid].update({
						'full_working':False,
					})
		# Update Attributes Worked hours
		for eid, employee_atds in res_atds.iteritems():
			not_approved_count = 0
			for d,atd_data in employee_atds.iteritems():
				# res_atds[eid][d]['missing_hours'] = atd_data['full_hours'] - atd_data['worked_hours']
				if (atd_data['worked_hours'] < atd_data['full_hours']) and not atd_data['leave']:
					print '\n 2 missing hours',atd_data['missing_hours']
					atd_data['missing_hours'] = atd_data['full_hours'] - atd_data['worked_hours']
					not_approved_count += 1
					print '\n 3 missing hours',atd_data['missing_hours']
				if atd_data['type'] == 'leave':
					if (atd_data['waiting_approved_leave_count'] > 0):
						atd_data['bg_class'] = 'danger'
					else:
						atd_data['bg_class'] = 'success'

			if not_approved_count > 0:
				res_attrs[eid].update({
					'full_working': False,
					'no_approved_leave_count': not_approved_count,
				})
		# Update Attributes
		for eid, attr in res_attrs.iteritems():
			# Get not approved leave count
			res_attrs[eid]['approved_leave_count'] = len(res_attrs[eid]['approved_leave_ids'])
			res_attrs[eid]['class'] = " ".join(["full_working" if attr['full_working'] else "", 
				"approved_leaves" if attr['approved_leave_count'] else "", 
				"no_approved_leaves" if attr['no_approved_leave_count'] else "",
				"have_ot" if attr['ot_worked_hours'] > 0 else "",
			])

		# print '\n\n ===> RES::attributes',res_attrs
		# print '\n\n ===> RES::leaves',res_leaves
		return {
			'attendances': res_atds,
			'attributes': res_attrs,
			'leaves': res_leaves,
			# 'holidays': HOLIDAYS,
		}

	def get_missing_hours(self, leave_time, comeback_time, calendar):
		hours = 0.0
		for cal in calendar:
			hours+=self.env['resource.calendar'].get_working_hours_of_date(leave_time,comeback_time,default_interval=(cal.hour_from,cal.hour_to))
		return hours


	def get_next_leave(self, atds, date_start, date_end,calendar, eid):
		"""
		:param list<hr.attendace> atds: employee attendance
		:param datetime date_start: time point where next leave calculate from
		:param datetime date_end: time point where next leave calculate to
		:param hr.calendar calendar: employee calendar
		:return date_from date_to of next leave
		:return (None, None) if cant find next leave
		"""
		if(date_start is str):
			date_start = datetime.strptime(date_start, "%Y-%m-%d %H:%M:%S")
		if(date_end is str):
			date_end = datetime.strptime(date_end, "%Y-%m-%d %H:%M:%S")
		atds=atds.filtered(lambda a: fields.Datetime.context_timestamp(a,datetime.strptime(a.check_out, "%Y-%m-%d %H:%M:%S")).replace(tzinfo=None)>date_start)
		date_from = None
		date_to = None

		index = 0
		leave_time = date_start
		comeback_time = None
		while index<len(atds):
			comeback_time = fields.Datetime.context_timestamp(atds[index],datetime.strptime(atds[index].check_in,"%Y-%m-%d %H:%M:%S")).replace(tzinfo=None)
			if (self.get_missing_hours(leave_time,comeback_time,calendar)):
				date_from = leave_time
				date_to = comeback_time
				break
			else:
				leave_time=fields.Datetime.context_timestamp(atds[index],datetime.strptime(atds[index].check_out,"%Y-%m-%d %H:%M:%S")).replace(tzinfo=None)
				index+=1
		comeback_time = date_end

		if(self.get_missing_hours(leave_time,comeback_time,calendar)):
			date_from = leave_time
			date_to = comeback_time
		# else date_from = date_to = None

		if len(self.env['hr.holidays'].search([('employee_id','=',eid),('type','=','remove'),('holiday_type','=','employee')]).filtered(lambda l: l.date_from == date_from and l.date_to == date_to)):
			#leave has been registered
			date_from, date_to = self.get_next_leave(atds, date_to, date_end, calendar)
		if(date_from != None and date_to !=None):
			date_from = date_from.strftime("%Y-%m-%d %H:%M:%S")
			date_to = date_to.strftime("%Y-%m-%d %H:%M:%S")
		return date_from, date_to

	@api.model
	def get_new_leave_request_params(self,eid,date_start):
		datetime_fmt = "%Y-%m-%d %H:%M:%S"
		atds=self.env['hr.attendance'].search([('employee_id','=',eid),('check_in_date','=',date_start)]).filtered(lambda a: fields.Datetime.context_timestamp(a,datetime.strptime(a.check_out, datetime_fmt)).replace(tzinfo=None)>datetime.strptime(date_start, "%Y-%m-%d"))

		##TODO: if atds is empty, don not do anything
		##TODO: holidays thing here
		# holidays = [datetime]
		# for holiday in holidays:
		# 	atds= atds.filtered(lambda a: a.check_in_date == holiday)

		ecal = self.env['hr.employee'].browse(eid).calendar_id
		if (date_start is not datetime):
			date_start = datetime.combine(datetime.strptime(date_start, "%Y-%m-%d"),time(23,59,59))
		date_end = date_start.replace(hour=0, minute=0, second=0)
	
		calendar= self.env['resource.calendar.attendance'].search([('date_from','<=',date_start.date()),('date_to','>=',date_start.date()),('dayofweek','=',date_start.date().weekday()),('calendar_id','=',ecal.id)])
		if not calendar:
			calendar = self.env['resource.calendar.attendance'].search([('date_from','=',None),('date_to','=',None),('dayofweek','=',date_start.date().weekday()),('calendar_id','=',ecal.id)])
		
		date_from=date_to=None
		# for cal in calendar:
		# 	date_start = min(date_start,datetime.combine(date_start.date(),time())+timedelta(hours=cal.hour_from))
		# 	date_end = max(date_end,datetime.combine(date_end.date(),time())+timedelta(hours=cal.hour_to))



		# date_from, date_to = self.get_next_leave(atds,date_start,date_end,calendar,eid)
		#return (None, None) if no more leave
		for cal in calendar:
			start_dt = datetime.combine(date_start.date(),time())+timedelta(hours=cal.hour_from)
			end_dt = datetime.combine(date_end.date(),time())+timedelta(hours=cal.hour_to)
			date_from, date_to = self.get_next_leave(atds,start_dt,end_dt,calendar,eid)
			if(date_from != None and date_to!=None):
				break
		# if(date_from == None and date_to==None):
		# TODO:Work needed
		#convert back to UTC
		date_from = datetime.strptime(date_from,datetime_fmt)
		date_to =datetime.strptime(date_to,datetime_fmt)
		timezone = fields.Datetime.context_timestamp(atds,date_from).tzinfo
		date_from = timezone.localize(date_from).astimezone(pytz.UTC)
		date_to = timezone.localize(date_to).astimezone(pytz.UTC)
		date_from = date_from.strftime(datetime_fmt)
		date_to = date_to.strftime(datetime_fmt)
		return {
			'date_from': date_from,
			'date_to': date_to,
		}
		
	def _convert_utc_to_timezone(self,utc_datetime,output_fmt = "%Y-%m-%d %H:%M:%S"):
		if not utc_datetime:
			return False
		datetime_fmt = "%Y-%m-%d %H:%M:%S"
		if isinstance(utc_datetime, str):
			return fields.Datetime.context_timestamp(self, timestamp=datetime.strptime(utc_datetime, datetime_fmt)).strftime(output_fmt)
		elif isinstance(utc_datetime, datetime):
			return fields.Datetime.context_timestamp(self, timestamp=utc_datetime).strftime(output_fmt)
		else:
			return False

