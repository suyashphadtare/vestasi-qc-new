	# Copyright (c) 2013, New Indictrans Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import re
from frappe import _
from frappe.utils import cstr, flt, getdate, comma_and,cint

class QualityChecking(Document):
	def validate(self):
                self.validate_serial()
                #self.change_qcstatus()

	def validate_serial(self):
        	sample_serial_no_list=[]
        	for d in self.get('qc_serial'):
                	if d in sample_serial_no_list:
                        	frappe.msgprint("Sample serial number can not duplicate",raise_exception=1)
                    		sample_serial_no_list.append(d.sample_serial_no)
                    	if cint(re.findall('\\d+', d.serial_from)[0]) > cint(re.findall('\\d+', d.serial_to)[0]):
                        	frappe.msgprint("From Serial No must be less than To Serial No",raise_exception=1)

	def qc_result(self,serial_no):
        	parameters=self.get_parameteres()
      		result=self.get_result(parameters,serial_no)
       		return "Done"
	
	def get_parameteres(self):
		if self.item_code:
                	return frappe.db.sql("""select a.specification,a.min_value,a.max_value 
                		from `tabItem Quality Inspection Parameter` as a , 
                		tabItem as b where a.mandatory='Yes'
                		 and a.parent=b.name 
                		 and b.name='%s'
                		 and a.specification in ('Fe','Ca','Al','C','O2','Free Si','Alpha')"""%(self.item_code),as_list=1)

	def get_result(self,parameters,serial_no):
		icon_mapper={'Rejected':'icon-remove','Accepted':'icon-ok'}
		
        	for d in self.get('qc_serial'):
            		for data in parameters:
			
                		if d.sample_serial_no==serial_no:
                    			fieldname=frappe.db.sql("select fieldname from tabDocField where label='%s'"%(data[0]),as_list=1)
                    			if fieldname:
                        			if (data[1] and data[2]) and (flt(d.get(fieldname[0][0])) >= flt(data[1]) and flt(d.get(fieldname[0][0])) <= flt(data[2])):
										d.result='Accepted'
                             
                        			elif not data[2] and (flt(d.get(fieldname[0][0])) >= flt(data[1])):                                                
                           				d.result='Accepted'                  
                                
                        			elif not data[1] and (flt(d.get(fieldname[0][0])) <= flt(data[2])):
                            				d.result='Accepted'                         
                        
                        			else:
                        				d.result='Rejected'
                            				d.result_status='<icon class="icon-remove"></icon>'
							d.grade = self.get_rejected_grade(d)
                           				break

                				if(d.result=='Accepted'):
							d.grade = frappe.db.get_value('Item',self.item_code,'grade')
							d.result_status='<icon class="icon-ok"></icon>'

        	return d.result

	def get_rejected_grade(self, args):
		if args.sample_serial_no:
			return 'R' 

	
	def on_submit(self):
        	self.validate_qc_status()
        	self.change_qcstatus()

	def on_cancel(self):
    		self.change_qcstatus_on_cancel()

	
	def validate_qc_status(self):
        	for data in self.get('qc_serial'):
        		if data.result=='':
                		frappe.throw("QC Status Should be Either Accepted Or Rejected")
    
	
	def change_qcstatus(self):
		serials_qc_dic={}
		for data in self.get('qc_serial'):
			serials=frappe.db.sql("""select name from `tabSerial No` 
				where status='Available' 
				and name between '%s' and '%s' """%(data.serial_from,data.serial_to),as_list=1)
			for serial in serials:
				self.set_values_in_serial_qc(serial[0],data)
				grade=self.get_grade(serial[0],data)
				self.change_status(serial,data,grade)
				to_do=frappe.db.sql("""update `tabToDo` set status='Closed' where serial_no='%s'"""%(serial[0]))
				
	def get_grade(self,serial,data):
		sn=frappe.get_doc("Serial No",serial)
		psd_grade=sn.psd_grade
		sa_grade=sn.sa_grade
		if not psd_grade and not sa_grade:
			sn.grade=data.grade
		elif psd_grade=='R' and sa_grade=='R':
			sn.grade='R'
		elif psd_grade=='R' and sa_grade!='R':
			sn.grade='R '+cstr(sa_grade)
		elif data.grade=='R' and sa_grade=='R':
			sn.grade='R'
		elif data.grade!='R' and psd_grade!='R' and sa_grade=='R':
			sn.grade=cstr(data.grade)+' R'
		elif data.grade!='R' and psd_grade!='R' and sa_grade!='R':
			sn.grade=' R'
		elif data.grade=='R' and psd_grade=='R' and sa_grade!='R':
			sn.grade='R '+cstr(sa_grade)
		return sn.grade

	def change_status(self,serial,data,grade):
		serial_numbers=frappe.db.sql("""update `tabSerial No` 
			set qc_status='%s',grade='%s',qc_grade='%s'
			where name='%s'"""%(data.result,grade,data.grade,serial[0]))


	def set_values_in_serial_qc(self,serial,data):
			sn=frappe.get_doc("Serial No",serial)
			cl=sn.get('quality_parameters')
			temp=0
			if cl:
				for d in cl:
					if temp==0:
						d.fe=data.fe
						d.ca=data.ca
						d.al=data.al
						d.c=data.c
						d.alpha=data.alpha
						d.o2=data.o2
						d.free_si=data.free_si
						sn.save(ignore_permissions=True)
			else:
				qp=sn.append("quality_parameters",{})
				qp.fe=data.fe
				qp.ca=data.ca
				qp.al=data.al
				qp.c=data.c
				qp.alpha=data.alpha
				qp.o2=data.o2
				qp.free_si=data.free_si
				sn.save(ignore_permissions=True)

	def change_qcstatus_on_cancel(self):
		for data in self.get('qc_serial'):
			serials=frappe.db.sql("""select name from `tabSerial No` where status='Available' and name between '%s' and '%s' """%(data.serial_from,data.serial_to),as_list=1)
			for serial in serials:
				serial_numbers=frappe.db.sql("""update `tabSerial No` set qc_status='',qc_grade='' where name='%s'"""%(serial[0]))
				to_do=frappe.db.sql("""update `tabToDo` set status='Open' where serial_no='%s'"""%(serial[0]))
				frappe.db.sql("""delete from `tabQuality Paramter Values` where parent='%s'"""%(serial[0]))
				
 
