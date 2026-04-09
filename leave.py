from flask import Blueprint, request, jsonify
import pymysql
import uuid
from datetime import datetime, timedelta
from decorators import jwt_required
from connector import get_connection

leave_bp = Blueprint('leave', __name__)


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def _count_leave_days(from_date, to_date, day_type, org_id, cursor):
    """Count working days between two dates excluding weekends & org holidays."""
    if day_type == 'Half Day':
        return 0.5

    cursor.execute(
        "SELECT holiday_date FROM holidays "
        "WHERE org_id = %s AND holiday_date BETWEEN %s AND %s",
        (org_id, from_date, to_date)
    )
    holidays = {row['holiday_date'] for row in cursor.fetchall()}

    count = 0.0
    cur = from_date
    while cur <= to_date:
        if cur.weekday() < 5 and cur not in holidays:  # Mon–Fri, non-holiday
            count += 1.0
        cur += timedelta(days=1)
    return count


def _has_overlap(user_id, from_date, to_date, cursor, exclude_id=None):
    """Return True if employee already has Pending/Approved leave on these dates."""
    sql = (
        "SELECT id FROM leave_requests "
        "WHERE user_id = %s AND status IN ('Pending','Approved') "
        "  AND from_date <= %s AND to_date >= %s"
    )
    params = [user_id, to_date, from_date]
    if exclude_id:
        sql += " AND id != %s"
        params.append(exclude_id)
    cursor.execute(sql, params)
    return cursor.fetchone() is not None


def _auto_create_balance_for_employee(user_id, org_id, cursor, conn):
    """
    Call this inside add_emp() after inserting the employee.
    Creates a leave_balance row for every active leave type in the org.
    """
    year = datetime.now().year
    cursor.execute(
        "SELECT id, total_days FROM leave_types WHERE org_id = %s AND is_active = 1",
        (org_id,)
    )
    leave_types = cursor.fetchall()
    for lt in leave_types:
        bal_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT IGNORE INTO leave_balances "
            "(id, user_id, org_id, leave_type_id, total_days, used_days, remaining_days, year) "
            "VALUES (%s,%s,%s,%s,%s,0,%s,%s)",
            (bal_id, user_id, org_id, lt['id'], lt['total_days'], lt['total_days'], year)
        )
    conn.commit()


def _auto_create_balance_for_leave_type(leave_type_id, total_days, org_id, cursor, conn):
    """
    Called when a new leave type is created.
    Creates a leave_balance row for every active employee in the org.
    """
    year = datetime.now().year
    cursor.execute(
        "SELECT id FROM users WHERE org_id = %s AND role = 'EMP' AND status = 'Active'",
        (org_id,)
    )
    employees = cursor.fetchall()
    for emp in employees:
        bal_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT IGNORE INTO leave_balances "
            "(id, user_id, org_id, leave_type_id, total_days, used_days, remaining_days, year) "
            "VALUES (%s,%s,%s,%s,%s,0,%s,%s)",
            (bal_id, emp['id'], org_id, leave_type_id, total_days, total_days, year)
        )
    conn.commit()


# ══════════════════════════════════════════════════════════════
#  LEAVE TYPES  — Manager creates / views / deletes
# ══════════════════════════════════════════════════════════════

@leave_bp.route('/add_leave_type', methods=['POST'])
@jwt_required
def add_leave_type(id=None, org_id=None, role=None, org_name=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data        = request.json
        name        = data.get('name')
        total_days  = data.get('total_days')
        description = data.get('description', '')

        if not name or total_days is None:
            return jsonify({'status': 'error', 'message': 'name and total_days are required'})

        new_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO leave_types (id, org_id, name, total_days, description, is_active, created_by, created_at) "
            "VALUES (%s,%s,%s,%s,%s,1,%s,NOW())",
            (new_id, org_id, name, total_days, description, id)
        )
        conn.commit()

        # Auto-create balance for all existing employees in this org
        _auto_create_balance_for_leave_type(new_id, total_days, org_id, cursor, conn)

        return jsonify({'status': 'success', 'message': 'Leave Type Added Successfully'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@leave_bp.route('/get_leave_types', methods=['GET'])
@jwt_required
def get_leave_types(id=None, org_id=None, role=None, org_name=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute(
            "SELECT * FROM leave_types WHERE org_id = %s AND is_active = 1 ORDER BY name",
            (org_id,)
        )
        leave_types = cursor.fetchall()

        return jsonify({
            'status': 'success',
            'message': 'Leave Types Fetched Successfully',
            'leave_types': leave_types
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@leave_bp.route('/delete_leave_type', methods=['POST'])
@jwt_required
def delete_leave_type(id=None, org_id=None, role=None, org_name=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data          = request.json
        leave_type_id = data.get('leave_type_id')

        cursor.execute(
            "UPDATE leave_types SET is_active = 0 WHERE id = %s AND org_id = %s",
            (leave_type_id, org_id)
        )
        conn.commit()

        return jsonify({'status': 'success', 'message': 'Leave Type Deleted Successfully'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ══════════════════════════════════════════════════════════════
#  LEAVE BALANCE  — View balance
# ══════════════════════════════════════════════════════════════

@leave_bp.route('/get_leave_balance', methods=['GET'])
@jwt_required
def get_leave_balance(id=None, org_id=None, role=None, org_name=None):
    """Employee sees own balance. Manager can pass ?user_id= to view any employee."""
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        target_user = request.args.get('user_id', id)
        year        = request.args.get('year', datetime.now().year)

        cursor.execute(
            """
            SELECT lb.*, lt.name AS leave_type_name
            FROM leave_balances lb
            JOIN leave_types lt ON lb.leave_type_id = lt.id
            WHERE lb.user_id = %s AND lb.org_id = %s AND lb.year = %s AND lt.is_active = 1
            ORDER BY lt.name
            """,
            (target_user, org_id, year)
        )
        balances = cursor.fetchall()

        return jsonify({
            'status': 'success',
            'message': 'Leave Balances Fetched Successfully',
            'balances': balances
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ══════════════════════════════════════════════════════════════
#  APPLY LEAVE  — Employee applies
# ══════════════════════════════════════════════════════════════

@leave_bp.route('/apply_leave', methods=['POST'])
@jwt_required
def apply_leave(id=None, org_id=None, role=None, org_name=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data          = request.json
        leave_type_id = data.get('leave_type_id')
        from_date_str = data.get('from_date')
        to_date_str   = data.get('to_date')
        day_type      = data.get('day_type', 'Full Day')   # 'Full Day' | 'Half Day'
        reason        = data.get('reason', '')
        year          = datetime.now().year

        if not leave_type_id or not from_date_str or not to_date_str:
            return jsonify({'status': 'error', 'message': 'leave_type_id, from_date, to_date are required'})

        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        to_date   = datetime.strptime(to_date_str,   '%Y-%m-%d').date()

        if from_date > to_date:
            return jsonify({'status': 'error', 'message': 'from_date cannot be after to_date'})

        # Half-day only on a single date
        if day_type == 'Half Day' and from_date != to_date:
            return jsonify({'status': 'error', 'message': 'Half Day leave is only allowed for a single date'})

        # Count working days
        leave_days = _count_leave_days(from_date, to_date, day_type, org_id, cursor)

        if leave_days <= 0:
            return jsonify({'status': 'error', 'message': 'Selected dates have no working days'})

        # Check overlap
        if _has_overlap(id, from_date, to_date, cursor):
            return jsonify({'status': 'error', 'message': 'You already have a leave overlapping these dates'})

        # Check balance
        cursor.execute(
            "SELECT * FROM leave_balances WHERE user_id = %s AND leave_type_id = %s AND year = %s",
            (id, leave_type_id, year)
        )
        balance = cursor.fetchone()

        if not balance:
            return jsonify({'status': 'error', 'message': 'No leave balance found for this leave type'})

        if float(balance['remaining_days']) < leave_days:
            return jsonify({
                'status': 'error',
                'message': f"Insufficient balance. Available: {balance['remaining_days']} days, Requested: {leave_days} days"
            })

        # Insert leave request
        new_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO leave_requests "
            "(id, user_id, org_id, leave_type_id, from_date, to_date, leave_days, day_type, reason, status, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Pending',NOW())",
            (new_id, id, org_id, leave_type_id, from_date, to_date, leave_days, day_type, reason)
        )
        conn.commit()

        return jsonify({'status': 'success', 'message': 'Leave Applied Successfully'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@leave_bp.route('/get_my_leaves', methods=['GET'])
@jwt_required
def get_my_leaves(id=None, org_id=None, role=None, org_name=None):
    """Employee views their own leave history."""
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        status_filter = request.args.get('status', '')

        sql = """
            SELECT lr.*, lt.name AS leave_type_name,
                   u.Name AS reviewer_name
            FROM leave_requests lr
            JOIN leave_types lt ON lr.leave_type_id = lt.id
            LEFT JOIN users u ON lr.reviewed_by = u.id
            WHERE lr.user_id = %s AND lr.org_id = %s
        """
        params = [id, org_id]

        if status_filter:
            sql += " AND lr.status = %s"
            params.append(status_filter)

        sql += " ORDER BY lr.created_at DESC"
        cursor.execute(sql, params)
        leaves = cursor.fetchall()

        for leave in leaves:
            for key in ['from_date', 'to_date', 'reviewed_at', 'created_at']:
                if leave.get(key) and hasattr(leave[key], 'strftime'):
                    leave[key] = str(leave[key])

        return jsonify({
            'status': 'success',
            'message': 'Leave History Fetched Successfully',
            'leaves': leaves
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ══════════════════════════════════════════════════════════════
#  MANAGER — View, Approve, Reject leave requests
# ══════════════════════════════════════════════════════════════

@leave_bp.route('/get_leave_requests', methods=['GET'])
@jwt_required
def get_leave_requests(id=None, org_id=None, role=None, org_name=None):
    """Manager views all leave requests in their org. Pass ?status=Pending to filter."""
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        status_filter = request.args.get('status', '')

        sql = """
            SELECT lr.*, lt.name AS leave_type_name,
                   u.Name AS employee_name, u.Email AS employee_email,
                   rv.Name AS reviewer_name
            FROM leave_requests lr
            JOIN leave_types lt ON lr.leave_type_id = lt.id
            JOIN users u ON lr.user_id = u.id
            LEFT JOIN users rv ON lr.reviewed_by = rv.id
            WHERE lr.org_id = %s
        """
        params = [org_id]

        if status_filter:
            sql += " AND lr.status = %s"
            params.append(status_filter)

        sql += " ORDER BY lr.created_at DESC"
        cursor.execute(sql, params)
        requests_list = cursor.fetchall()

        for r in requests_list:
            for key in ['from_date', 'to_date', 'reviewed_at', 'created_at']:
                if r.get(key) and hasattr(r[key], 'strftime'):
                    r[key] = str(r[key])

        return jsonify({
            'status': 'success',
            'message': 'Leave Requests Fetched Successfully',
            'leave_requests': requests_list
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@leave_bp.route('/approve_leave', methods=['POST'])
@jwt_required
def approve_leave(id=None, org_id=None, role=None, org_name=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data       = request.json
        request_id = data.get('request_id')
        comment    = data.get('comment', '')
        year       = datetime.now().year

        # Fetch the pending leave request
        cursor.execute(
            "SELECT * FROM leave_requests WHERE id = %s AND org_id = %s AND status = 'Pending'",
            (request_id, org_id)
        )
        leave_req = cursor.fetchone()

        if not leave_req:
            return jsonify({'status': 'error', 'message': 'Leave request not found or already reviewed'})

        # Verify balance is still sufficient
        cursor.execute(
            "SELECT * FROM leave_balances WHERE user_id = %s AND leave_type_id = %s AND year = %s",
            (leave_req['user_id'], leave_req['leave_type_id'], year)
        )
        balance = cursor.fetchone()

        if not balance or float(balance['remaining_days']) < float(leave_req['leave_days']):
            return jsonify({'status': 'error', 'message': 'Insufficient leave balance for this employee'})

        # Approve
        cursor.execute(
            "UPDATE leave_requests SET status='Approved', manager_comment=%s, "
            "reviewed_by=%s, reviewed_at=NOW() WHERE id=%s",
            (comment, id, request_id)
        )

        # Deduct balance
        cursor.execute(
            "UPDATE leave_balances "
            "SET used_days = used_days + %s, remaining_days = remaining_days - %s "
            "WHERE user_id = %s AND leave_type_id = %s AND year = %s",
            (leave_req['leave_days'], leave_req['leave_days'],
             leave_req['user_id'], leave_req['leave_type_id'], year)
        )
        conn.commit()

        return jsonify({'status': 'success', 'message': 'Leave Approved Successfully'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@leave_bp.route('/reject_leave', methods=['POST'])
@jwt_required
def reject_leave(id=None, org_id=None, role=None, org_name=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data       = request.json
        request_id = data.get('request_id')
        comment    = data.get('comment', '')

        cursor.execute(
            "SELECT * FROM leave_requests WHERE id = %s AND org_id = %s AND status = 'Pending'",
            (request_id, org_id)
        )
        leave_req = cursor.fetchone()

        if not leave_req:
            return jsonify({'status': 'error', 'message': 'Leave request not found or already reviewed'})

        cursor.execute(
            "UPDATE leave_requests SET status='Rejected', manager_comment=%s, "
            "reviewed_by=%s, reviewed_at=NOW() WHERE id=%s",
            (comment, id, request_id)
        )
        conn.commit()

        return jsonify({'status': 'success', 'message': 'Leave Rejected Successfully'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ══════════════════════════════════════════════════════════════
#  HOLIDAYS  — Manager adds / views / deletes
# ══════════════════════════════════════════════════════════════

@leave_bp.route('/add_holiday', methods=['POST'])
@jwt_required
def add_holiday(id=None, org_id=None, role=None, org_name=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data         = request.json
        name         = data.get('name')
        holiday_date = data.get('holiday_date')
        description  = data.get('description', '')

        if not name or not holiday_date:
            return jsonify({'status': 'error', 'message': 'name and holiday_date are required'})

        new_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO holidays (id, org_id, name, holiday_date, description, created_by, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,NOW())",
            (new_id, org_id, name, holiday_date, description, id)
        )
        conn.commit()

        return jsonify({'status': 'success', 'message': 'Holiday Added Successfully'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@leave_bp.route('/get_holidays', methods=['GET'])
@jwt_required
def get_holidays(id=None, org_id=None, role=None, org_name=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        year = request.args.get('year', datetime.now().year)

        cursor.execute(
            "SELECT * FROM holidays WHERE org_id = %s AND YEAR(holiday_date) = %s "
            "ORDER BY holiday_date ASC",
            (org_id, year)
        )
        holidays = cursor.fetchall()

        for h in holidays:
            if h.get('holiday_date') and hasattr(h['holiday_date'], 'strftime'):
                h['holiday_date'] = str(h['holiday_date'])
            if h.get('created_at') and hasattr(h['created_at'], 'strftime'):
                h['created_at'] = str(h['created_at'])

        return jsonify({
            'status': 'success',
            'message': 'Holidays Fetched Successfully',
            'holidays': holidays
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@leave_bp.route('/delete_holiday', methods=['POST'])
@jwt_required
def delete_holiday(id=None, org_id=None, role=None, org_name=None):
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        data       = request.json
        holiday_id = data.get('holiday_id')

        cursor.execute(
            "DELETE FROM holidays WHERE id = %s AND org_id = %s",
            (holiday_id, org_id)
        )
        conn.commit()

        return jsonify({'status': 'success', 'message': 'Holiday Deleted Successfully'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ══════════════════════════════════════════════════════════════
#  MANAGER — View employee leave summary
# ══════════════════════════════════════════════════════════════

@leave_bp.route('/get_employee_leave_summary', methods=['GET'])
@jwt_required
def get_employee_leave_summary(id=None, org_id=None, role=None, org_name=None):
    """
    Manager selects an employee and sees:
    - Leave balance (all types)
    - Full leave history (with half/full day, status, reason, etc.)
    Pass ?user_id=<employee_id>&year=<year>
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        user_id = request.args.get('user_id')
        year    = request.args.get('year', datetime.now().year)

        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id is required'})

        # Make sure employee belongs to this org
        cursor.execute(
            "SELECT id, Name, Email FROM users WHERE id = %s AND org_id = %s AND role = 'EMP'",
            (user_id, org_id)
        )
        employee = cursor.fetchone()

        if not employee:
            return jsonify({'status': 'error', 'message': 'Employee not found in your organisation'})

        # Leave balances
        cursor.execute(
            """
            SELECT lb.*, lt.name AS leave_type_name
            FROM leave_balances lb
            JOIN leave_types lt ON lb.leave_type_id = lt.id
            WHERE lb.user_id = %s AND lb.org_id = %s AND lb.year = %s AND lt.is_active = 1
            ORDER BY lt.name
            """,
            (user_id, org_id, year)
        )
        balances = cursor.fetchall()

        # Full leave history
        cursor.execute(
            """
            SELECT lr.*, lt.name AS leave_type_name,
                   rv.Name AS reviewer_name
            FROM leave_requests lr
            JOIN leave_types lt ON lr.leave_type_id = lt.id
            LEFT JOIN users rv ON lr.reviewed_by = rv.id
            WHERE lr.user_id = %s AND lr.org_id = %s
            ORDER BY lr.created_at DESC
            """,
            (user_id, org_id)
        )
        leaves = cursor.fetchall()

        # Serialize dates
        for leave in leaves:
            for key in ['from_date', 'to_date', 'reviewed_at', 'created_at']:
                if leave.get(key) and hasattr(leave[key], 'strftime'):
                    leave[key] = str(leave[key])

        # Summary counts
        total_taken    = sum(float(l['leave_days']) for l in leaves if l['status'] == 'Approved')
        total_pending  = sum(float(l['leave_days']) for l in leaves if l['status'] == 'Pending')
        total_rejected = len([l for l in leaves if l['status'] == 'Rejected'])
        half_day_count = len([l for l in leaves if l['day_type'] == 'Half Day' and l['status'] == 'Approved'])
        full_day_count = len([l for l in leaves if l['day_type'] == 'Full Day' and l['status'] == 'Approved'])

        return jsonify({
            'status':   'success',
            'message':  'Employee Leave Summary Fetched Successfully',
            'employee': employee,
            'year':     year,
            'summary': {
                'total_approved_days': total_taken,
                'total_pending_days':  total_pending,
                'total_rejected':      total_rejected,
                'approved_half_days':  half_day_count,
                'approved_full_days':  full_day_count,
            },
            'balances': balances,
            'leaves':   leaves
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@leave_bp.route('/get_org_employees', methods=['GET'])
@jwt_required
def get_org_employees(id=None, org_id=None, role=None, org_name=None):
    """
    Returns all active employees in the org for the manager's dropdown.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute(
            "SELECT id, Name, Email FROM users "
            "WHERE org_id = %s AND role = 'EMP' AND status = 'Active' "
            "ORDER BY Name ASC",
            (org_id,)
        )
        employees = cursor.fetchall()

        return jsonify({
            'status':    'success',
            'message':   'Employees Fetched Successfully',
            'employees': employees
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()        


















