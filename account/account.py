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
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute("select u.Name,s.user_id, s.base_salary, s.agp,s.da,s.dp,s.hra,s.tra,s.cla from users u inner join salary_detailes s on u.id = s.user_id where s.org_id = %s",(org_id,))
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

# Check which employees already have salary saved for a given month ──
@account_bp.route('/get_monthly_salary_records', methods=['GET'])
@jwt_required
def get_monthly_salary_records(id=None, role=None, org_id=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        salary_month = request.args.get('salary_month')
        if not salary_month:
            return jsonify({'status': 'error', 'message': 'salary_month is required'}), 400

        cursor.execute(
            "SELECT user_id, adj_base, adj_agp, adj_da, adj_dp, adj_hra, adj_tra, adj_cla, "
            "       pt, pf, other_deduction, absent_days_deduction, gross_salary, net_salary "
            "FROM staff_salary_record "
            "WHERE org_id = %s AND salary_month = %s",
            (org_id, salary_month)
        )
        records = cursor.fetchall()
        return jsonify({
            'status': 'success',
            'records': records
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

    
@account_bp.route('/emp_salary', methods=['GET','POST'])
@jwt_required
def emp_salary(id = None, org_id = None, role = None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data = request.json
        
        salary_month = data.get('salary_month')
        salary_date = data.get('salary_date')
        sal_record = str(uuid.uuid4())

        user_id = data.get('user_id')
        base_salary = float(data.get('base_salary'))
        agp = float(data.get('agp',0))
        da = float(data.get('da',0))
        dp = float(data.get('dp',0))
        hra = float(data.get('hra',0))
        tra = float(data.get('tra',0))
        cla = float(data.get('cla',0))
        pt = float(data.get('pt',0)) #this is the new it can be manual entry from frontend.
        pf = float(data.get('pf',0)) #this is the new it can be manual entry from frontend.
        other_deduction = float(data.get('other_deduction',0)) #this is the new it can be manual entry from frontend.
        
        absent_days_deduction =float(data.get('absent_days_deduction',0)) #this is the new it can be manual entry from frontend.

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



# Update a single employee's already-saved salary for a given month ──
@account_bp.route('/update_emp_salary', methods=['PUT'])
@jwt_required
def update_emp_salary(id=None, org_id=None, role=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data = request.json
        user_id = data.get('user_id')
        salary_month = data.get('salary_month')

        if not user_id or not salary_month:
            return jsonify({'status': 'error', 'message': 'user_id and salary_month are required'}), 400

        # Guard: must have an existing record for this month
        cursor.execute(
            "SELECT id FROM staff_salary_record WHERE user_id = %s AND org_id = %s AND salary_month = %s",
            (user_id, org_id, salary_month)
        )
        if not cursor.fetchone():
            return jsonify({
                'status': 'fail',
                'message': 'No saved record found for this employee and month. Save first before updating.'
            })

        base_salary = data.get('base_salary', 0)
        agp         = data.get('agp', 0)
        da          = data.get('da', 0)
        dp          = data.get('dp', 0)
        hra         = data.get('hra', 0)
        tra         = data.get('tra', 0)
        cla         = data.get('cla', 0)
        pt          = data.get('pt', 0)
        pf          = data.get('pf', 0)
        other_deduction       = data.get('other_deduction', 0)
        absent_days_deduction = data.get('absent_days_deduction', 0)

        gross_salary = base_salary + agp + da + dp + hra + tra + cla
        net_salary   = gross_salary - (pf + pt + other_deduction + absent_days_deduction)

        cursor.execute(
            "UPDATE staff_salary_record SET "
            "adj_base=%s, adj_agp=%s, adj_da=%s, adj_dp=%s, adj_hra=%s, adj_tra=%s, adj_cla=%s, "
            "pt=%s, pf=%s, other_deduction=%s, absent_days_deduction=%s, "
            "gross_salary=%s, net_salary=%s "
            "WHERE user_id=%s AND org_id=%s AND salary_month=%s",
            (base_salary, agp, da, dp, hra, tra, cla,
             pt, pf, other_deduction, absent_days_deduction,
             gross_salary, net_salary,
             user_id, org_id, salary_month)
        )
        conn.commit()
        return jsonify({
            'status': 'success',
            'message': f'Salary updated successfully for {salary_month}.'
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


#Salary Summary Part
@account_bp.route('/salary_summary', methods=['GET'])
@jwt_required
def salary_summary(id = None, org_id = None, role = None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        salary_month = request.args.get('salary_month')
        if not salary_month:
            return jsonify({'status':'fail', 'message':'Salary Records Not Found For Selected Month'})
        
        cursor.execute("select SUM(adj_base) as base, SUM(adj_agp) as agp, SUM(adj_da) as da, SUM(adj_dp) as dp, SUM(adj_hra) as hra, SUM(adj_tra) as tra, SUM(adj_cla) as cla, SUM(pt) as pt, SUM(pf) as pf, SUM(other_deduction) as other_deduction, SUM(absent_days_deduction) as absent_days_deduction, SUM(net_salary) as net_salary, (SUM(adj_base) + SUM(adj_agp) + SUM(adj_da) + SUM(adj_dp) + SUM(adj_hra) + SUM(adj_tra) + SUM(adj_cla)) as earnings, (SUM(pt)+SUM(pf)+SUM(other_deduction)+SUM(absent_days_deduction)) as deductions from staff_salary_record where org_id = %s and salary_month = %s",(org_id,salary_month))
        summary = cursor.fetchone()

        return jsonify({
            'status':'success',
            'message':'All Salary Summary Loaded',
            'summary':summary
        })
    except Exception as e:
        return jsonify({
            'status':'error',
            'message':str(e)
        })
    
    finally:
        cursor.close()
        conn.close()


#Salary Disbursement
@account_bp.route('/salary_disbursement', methods=['GET'])
@jwt_required
def salary_disbursement(id = None, org_id = None, role = None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        salary_month = request.args.get('salary_month')
        if not salary_month:
            return jsonify({
                'status':'fail',
                'message':'Month Selected have no salary detailes'
            })

        cursor.execute("select u.Name, sd.bank_acc_no, sd.ifsc_code, sd.bank_name, ss.net_salary from users u join salary_detailes sd ON u.id = sd.user_id join staff_salary_record ss ON u.id = ss.user_id where ss.org_id = %s and ss.salary_month = %s",(org_id, salary_month))
        users = cursor.fetchall()
        
        return jsonify({
            'status':'success',
            'message':f'All Salary Records For Selected Month {salary_month} fetched successfully.',
            'users': users
        })

    except Exception as e:
        return jsonify({
            'status':'error',
            'message':str(e)
        })
    
    finally:
        cursor.close()
        conn.close()

