from flask import request, jsonify, Blueprint
import pymysql
from connector import get_connection
from decorators import jwt_required
import uuid

account_bp = Blueprint('account',__name__)


@account_bp.route('/get_salary_details', methods=['GET'])
@jwt_required
def get_salary_detailes(id = None, role= None, org_id=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("select u.Name,s.user_id, s.base_salary, s.agp,s.da,s.dp,s.hra,s.tra,s.cla from users u inner join salary_detailes s on u.org_id = s.org_id where s.org_id = %s",(org_id,))
        emp = cursor.fetchall()
        return jsonify({
            'status':'success',
            'message':'salary records fetched successfully.',
            'emp':emp

        })
    except Exception as e:
        return jsonify({
            'status':'error',
            'message':str(e)
        })
    finally:
        cursor.close()
        conn.close()
    

@account_bp.route('/emp_salary', methods=['GET','POST'])
@jwt_required
def emp_salary(id = None, org_id = None, role = None):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        data = request.json
        
        salary_month = data.get('salary_month')
        salary_date = data.get('salary_date')
        sal_record = str(uuid.uuid4())

        user_id = data.get('user_id')
        base_salary = data.get('base_salary')
        agp = data.get('agp')
        da = data.get('da')
        dp = data.get('dp')
        hra = data.get('hra')
        tra = data.get('tra')
        cla = data.get('cla')
        pt = data.get('pt') #this is the new it can be manual entry from frontend.
        pf = data.get('pf') #this is the new it can be manual entry from frontend.
        other_deduction = data.get('other_deduction') #this is the new it can be manual entry from frontend.
        
        absent_days_deduction =data.get('absent_days_deduction') #this is the new it can be manual entry from frontend.

        gross_salary = base_salary + agp + da + dp + hra + tra + cla

        net_salary = gross_salary - (pf + pt + other_deduction + absent_days_deduction)

        cursor.execute("select id from staff_salary_record where user_id = %s AND org_id = %s AND salary_month =%s",(user_id,org_id,salary_month))
        sal_user = cursor.fetchone()
        if sal_user:
            return jsonify({
                'status':'fail',
                'message': 'Salary Already Recorded For This Employee'
            })
        else:
            cursor.execute("insert into staff_salary_record(id,user_id,org_id,adj_base,adj_agp,adj_da,adj_dp,adj_hra,adj_tra,adj_cla,pt,pf,other_deduction,absent_days_deduction,gross_salary,net_salary,salary_month,salary_date,created_by,created_date) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())",(sal_record,user_id,org_id,base_salary,agp,da,dp,hra,tra,cla,pt,pf,other_deduction,absent_days_deduction,gross_salary,net_salary,salary_month,salary_date,id))
            conn.commit()
            return jsonify({
                'status':'success',
                'message':f'{salary_month} Months Salary Recorded Successfully.'
            })
            
    except Exception as e:
        return jsonify({
            'status':'error',
            'message':str(e)
        })
    
    finally:
        cursor.close()
        conn.close()