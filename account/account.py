from flask import request, jsonify, Blueprint, send_file
import pymysql
from connector import get_connection
from decorators import jwt_required
import uuid, io

from datetime import datetime

# ── ReportLab ──────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

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
        
        cursor.execute("select COUNT(user_id) as total_emp, SUM(adj_base) as base, SUM(adj_agp) as agp, SUM(adj_da) as da, SUM(adj_dp) as dp, SUM(adj_hra) as hra, SUM(adj_tra) as tra, SUM(adj_cla) as cla, SUM(pt) as pt, SUM(pf) as pf, SUM(other_deduction) as other_deduction, SUM(absent_days_deduction) as absent_days_deduction, SUM(net_salary) as net_salary, (SUM(adj_base) + SUM(adj_agp) + SUM(adj_da) + SUM(adj_dp) + SUM(adj_hra) + SUM(adj_tra) + SUM(adj_cla)) as earnings, (SUM(pt)+SUM(pf)+SUM(other_deduction)+SUM(absent_days_deduction)) as deductions from staff_salary_record where org_id = %s and salary_month = %s",(org_id,salary_month))
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

        cursor.execute("select u.id as user_id,u.Name, sd.bank_acc_no, sd.ifsc_code, sd.bank_name, ss.net_salary from users u join salary_detailes sd ON u.id = sd.user_id join staff_salary_record ss ON u.id = ss.user_id where ss.org_id = %s and ss.salary_month = %s",(org_id, salary_month))
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


# ── Colour palette ──────────────────────────────────────────────────────────
PRIMARY   = colors.HexColor('#1a3c5e')   # dark navy
ACCENT    = colors.HexColor('#2e86c1')   # mid blue
LIGHT_BG  = colors.HexColor('#eaf4fb')  # very light blue
ALT_ROW   = colors.HexColor('#f4f8fc')  # alternate row tint
GREEN     = colors.HexColor('#1e8449')
RED       = colors.HexColor('#c0392b')
WHITE     = colors.white
GREY_LINE = colors.HexColor('#bdc3c7')


# ════════════════════════════════════════════════════════════════════════════
#  HELPER – shared styles
# ════════════════════════════════════════════════════════════════════════════
def _styles():
    base = getSampleStyleSheet()
    styles = {
        'title': ParagraphStyle(
            'DocTitle', fontSize=18, fontName='Helvetica-Bold',
            textColor=PRIMARY, alignment=TA_CENTER, spaceAfter=4
        ),
        'subtitle': ParagraphStyle(
            'DocSubtitle', fontSize=11, fontName='Helvetica',
            textColor=ACCENT, alignment=TA_CENTER, spaceAfter=2
        ),
        'meta': ParagraphStyle(
            'DocMeta', fontSize=9, fontName='Helvetica',
            textColor=colors.grey, alignment=TA_CENTER, spaceAfter=12
        ),
        'section': ParagraphStyle(
            'Section', fontSize=11, fontName='Helvetica-Bold',
            textColor=PRIMARY, spaceBefore=14, spaceAfter=6
        ),
        'footer': ParagraphStyle(
            'Footer', fontSize=8, fontName='Helvetica',
            textColor=colors.grey, alignment=TA_CENTER
        ),
        'normal': base['Normal'],
        'bold_right': ParagraphStyle(
            'BoldRight', fontSize=9, fontName='Helvetica-Bold',
            textColor=PRIMARY, alignment=TA_RIGHT
        ),
    }
    return styles


def _header_block(story, styles, title_text, salary_month, org_name=None):
    """Common header: title + month + optional org name."""
    story.append(Paragraph(title_text, styles['title']))
    if org_name:
        story.append(Paragraph(org_name, styles['subtitle']))
    story.append(Paragraph(f"Salary Month : {salary_month}", styles['meta']))
    story.append(Paragraph(
        f"Generated on : {datetime.now().strftime('%d %B %Y, %I:%M %p')}",
        styles['meta']
    ))
    story.append(HRFlowable(width='100%', thickness=1.5, color=ACCENT, spaceAfter=10))


def _currency(value):
    """Format a number as Indian-style currency string."""
    try:
        return f"\u20b9 {float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "\u20b9 0.00"


def _tbl_style_base():
    return [
        ('BACKGROUND',   (0, 0), (-1, 0),  PRIMARY),
        ('TEXTCOLOR',    (0, 0), (-1, 0),  WHITE),
        ('FONTNAME',     (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, 0),  9),
        ('ALIGN',        (0, 0), (-1, 0),  'CENTER'),
        ('BOTTOMPADDING',(0, 0), (-1, 0),  8),
        ('TOPPADDING',   (0, 0), (-1, 0),  8),
        ('FONTNAME',     (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',     (0, 1), (-1, -1), 8.5),
        ('ROWBACKGROUND',(0, 1), (-1, -1), [WHITE, ALT_ROW]),
        ('GRID',         (0, 0), (-1, -1), 0.4, GREY_LINE),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',   (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING',(0, 1), (-1, -1), 5),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]


# ════════════════════════════════════════════════════════════════════════════
#  1.  SALARY SUMMARY PDF
# ════════════════════════════════════════════════════════════════════════════
@account_bp.route('/salary_summary_pdf', methods=['GET'])
@jwt_required
def salary_summary_pdf(id=None, org_id=None, role=None):
    """
    GET /salary_summary_pdf?salary_month=2025-06
    Returns a downloadable PDF summarising the month's aggregate salary figures.
    """
    salary_month = request.args.get('salary_month')
    if not salary_month:
        return jsonify({'status': 'error', 'message': 'salary_month is required'}), 400

    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # ── Aggregate summary row ────────────────────────────────────────
        cursor.execute("""
            SELECT
                COUNT(user_id)                    AS total_employees,
                SUM(adj_base)                     AS base,
                SUM(adj_agp)                      AS agp,
                SUM(adj_da)                       AS da,
                SUM(adj_dp)                       AS dp,
                SUM(adj_hra)                      AS hra,
                SUM(adj_tra)                      AS tra,
                SUM(adj_cla)                      AS cla,
                SUM(adj_base + adj_agp + adj_da + adj_dp + adj_hra + adj_tra + adj_cla) AS gross_salary,
                SUM(pt)                           AS pt,
                SUM(pf)                           AS pf,
                SUM(other_deduction)              AS other_deduction,
                SUM(absent_days_deduction)        AS absent_days_deduction,
                SUM(pt + pf + other_deduction + absent_days_deduction) AS total_deductions,
                SUM(net_salary)                   AS net_salary
            FROM staff_salary_record
            WHERE org_id = %s AND salary_month = %s
        """, (org_id, salary_month))
        s = cursor.fetchone()

        if not s or s['total_employees'] == 0:
            return jsonify({
                'status': 'fail',
                'message': 'No salary records found for the selected month.'
            }), 404

        # ── Per-employee breakdown ───────────────────────────────────────
        cursor.execute("""
            SELECT u.Name,
                   ss.adj_base, ss.adj_agp, ss.adj_da, ss.adj_dp,
                   ss.adj_hra, ss.adj_tra, ss.adj_cla,
                   (ss.adj_base + ss.adj_agp + ss.adj_da + ss.adj_dp +
                    ss.adj_hra + ss.adj_tra + ss.adj_cla) AS gross,
                   ss.pt, ss.pf, ss.other_deduction, ss.absent_days_deduction,
                   (ss.pt + ss.pf + ss.other_deduction + ss.absent_days_deduction) AS total_ded,
                   ss.net_salary
            FROM staff_salary_record ss
            JOIN users u ON ss.user_id = u.id
            WHERE ss.org_id = %s AND ss.salary_month = %s
            ORDER BY u.Name
        """, (org_id, salary_month))
        employees = cursor.fetchall()

        # ── Build PDF ────────────────────────────────────────────────────
        buf    = io.BytesIO()
        doc    = SimpleDocTemplate(
            buf, pagesize=landscape(A4),
            leftMargin=1.5*cm, rightMargin=1.5*cm,
            topMargin=1.5*cm, bottomMargin=1.5*cm
        )
        styles = _styles()
        story  = []

        _header_block(story, styles, 'Salary Summary Report', salary_month)

        # ── KPI cards (single-row summary table) ─────────────────────────
        story.append(Paragraph('Organisation Summary', styles['section']))
        kpi_data = [
            ['Total Employees', 'Total Gross', 'Total Deductions', 'Total Net Payable'],
            [
                str(int(s['total_employees'] or 0)),
                _currency(s['gross_salary']),
                _currency(s['total_deductions']),
                _currency(s['net_salary']),
            ]
        ]
        kpi_tbl = Table(kpi_data, colWidths=[6*cm]*4, hAlign='CENTER')
        kpi_tbl.setStyle(TableStyle([
            *_tbl_style_base(),
            ('ALIGN',      (0, 1), (-1, 1), 'CENTER'),
            ('FONTNAME',   (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 1), (-1, 1), 11),
            ('TEXTCOLOR',  (3, 1), (3,  1), GREEN),
            ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BG),
        ]))
        story.append(kpi_tbl)
        story.append(Spacer(1, 8))

        # ── Earnings vs Deductions breakdown ─────────────────────────────
        story.append(Paragraph('Earnings & Deductions Breakdown', styles['section']))
        breakdown_data = [
            ['Component', 'Amount', '', 'Deduction', 'Amount'],
            ['Basic Salary', _currency(s['base']),   '', 'Professional Tax',    _currency(s['pt'])],
            ['AGP',          _currency(s['agp']),    '', 'Provident Fund',       _currency(s['pf'])],
            ['DA',           _currency(s['da']),     '', 'Other Deductions',     _currency(s['other_deduction'])],
            ['DP',           _currency(s['dp']),     '', 'Absent-day Deduction', _currency(s['absent_days_deduction'])],
            ['HRA',          _currency(s['hra']),    '', '', ''],
            ['TRA',          _currency(s['tra']),    '', '', ''],
            ['CLA',          _currency(s['cla']),    '', '', ''],
            ['Total Earnings', _currency(s['gross_salary']), '', 'Total Deductions', _currency(s['total_deductions'])],
        ]
        last = len(breakdown_data) - 1
        bd_tbl = Table(breakdown_data, colWidths=[5*cm, 4*cm, 0.5*cm, 5*cm, 4*cm], hAlign='CENTER')
        bd_tbl.setStyle(TableStyle([
            *_tbl_style_base(),
            ('SPAN',       (2, 0), (2, last)),           # divider column
            ('BACKGROUND', (2, 0), (2, last), WHITE),
            ('GRID',       (2, 0), (2, last), 0, WHITE),
            ('FONTNAME',   (0, last), (-1, last), 'Helvetica-Bold'),
            ('BACKGROUND', (0, last), (1,  last), LIGHT_BG),
            ('BACKGROUND', (3, last), (4,  last), LIGHT_BG),
            ('TEXTCOLOR',  (0, last), (1,  last), GREEN),
            ('TEXTCOLOR',  (3, last), (4,  last), RED),
            ('ALIGN',      (1, 1), (1, last), 'RIGHT'),
            ('ALIGN',      (4, 1), (4, last), 'RIGHT'),
        ]))
        story.append(bd_tbl)
        story.append(Spacer(1, 14))

        # ── Employee-wise detail table ────────────────────────────────────
        story.append(Paragraph('Employee-wise Detail', styles['section']))
        emp_headers = [
            'Name', 'Basic', 'AGP', 'DA', 'DP', 'HRA', 'TRA', 'CLA',
            'Gross', 'PT', 'PF', 'Other Ded.', 'Absent Ded.', 'Net Pay'
        ]
        emp_rows = [emp_headers]
        for e in employees:
            emp_rows.append([
                e['Name'],
                _currency(e['adj_base']), _currency(e['adj_agp']),
                _currency(e['adj_da']),   _currency(e['adj_dp']),
                _currency(e['adj_hra']),  _currency(e['adj_tra']),
                _currency(e['adj_cla']),
                _currency(e['gross']),
                _currency(e['pt']),       _currency(e['pf']),
                _currency(e['other_deduction']),
                _currency(e['absent_days_deduction']),
                _currency(e['net_salary']),
            ])

        col_w = [3.8*cm] + [1.8*cm]*13
        emp_tbl = Table(emp_rows, colWidths=col_w, repeatRows=1)
        emp_style = TableStyle(_tbl_style_base())
        emp_style.add('ALIGN', (1, 1), (-1, -1), 'RIGHT')
        emp_style.add('TEXTCOLOR', (-1, 1), (-1, -1), GREEN)   # net pay column
        emp_tbl.setStyle(emp_style)
        story.append(emp_tbl)

        story.append(Spacer(1, 20))
        story.append(HRFlowable(width='100%', thickness=0.5, color=GREY_LINE))
        story.append(Paragraph(
            'This is a system-generated report. No signature is required.',
            styles['footer']
        ))

        doc.build(story)
        buf.seek(0)
        filename = f"Salary_Summary_{salary_month}.pdf"
        return send_file(
            buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ════════════════════════════════════════════════════════════════════════════
#  2.  SALARY DISBURSEMENT PDF
# ════════════════════════════════════════════════════════════════════════════
@account_bp.route('/salary_disbursement_pdf', methods=['GET'])
@jwt_required
def salary_disbursement_pdf(id=None, org_id=None, role=None):
    """
    GET /salary_disbursement_pdf?salary_month=2025-06
    Returns a downloadable PDF listing every employee's bank details
    and net salary for the month — ready to hand to the bank / finance team.
    """
    salary_month = request.args.get('salary_month')
    if not salary_month:
        return jsonify({'status': 'error', 'message': 'salary_month is required'}), 400

    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute("""
            SELECT
                u.Name,
                sd.bank_acc_no,
                sd.ifsc_code,
                sd.bank_name,
                ss.net_salary
            FROM users u
            JOIN salary_detailes sd ON u.id = sd.user_id
            JOIN staff_salary_record ss ON u.id = ss.user_id
            WHERE ss.org_id = %s AND ss.salary_month = %s
            ORDER BY u.Name
        """, (org_id, salary_month))
        employees = cursor.fetchall()

        if not employees:
            return jsonify({
                'status': 'fail',
                'message': 'No disbursement records found for the selected month.'
            }), 404

        total_net = sum(float(e['net_salary'] or 0) for e in employees)

        # ── Build PDF ────────────────────────────────────────────────────
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=1.5*cm, rightMargin=1.5*cm,
            topMargin=1.5*cm, bottomMargin=2*cm
        )
        styles = _styles()
        story  = []

        _header_block(story, styles, 'Salary Disbursement Report', salary_month)

        # ── Summary strip ─────────────────────────────────────────────────
        summary_data = [
            ['Total Employees', 'Total Amount to Disburse'],
            [str(len(employees)), _currency(total_net)]
        ]
        sum_tbl = Table(summary_data, colWidths=[9*cm, 9*cm], hAlign='CENTER')
        sum_tbl.setStyle(TableStyle([
            *_tbl_style_base(),
            ('ALIGN',    (0, 1), (-1, 1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 12),
            ('TEXTCOLOR',(1, 1), (1,  1), GREEN),
            ('BACKGROUND',(0, 1), (-1, 1), LIGHT_BG),
        ]))
        story.append(sum_tbl)
        story.append(Spacer(1, 14))

        # ── Disbursement detail table ──────────────────────────────────────
        story.append(Paragraph('Employee Bank Details & Net Payable', styles['section']))
        headers = ['#', 'Employee Name', 'Bank Name', 'Account Number', 'IFSC Code', 'Net Salary']
        rows    = [headers]
        for idx, e in enumerate(employees, start=1):
            rows.append([
                str(idx),
                e['Name'],
                e['bank_name']    or '—',
                e['bank_acc_no']  or '—',
                e['ifsc_code']    or '—',
                _currency(e['net_salary']),
            ])

        # Total row
        rows.append(['', 'TOTAL', '', '', '', _currency(total_net)])

        col_w = [1*cm, 5.5*cm, 4*cm, 4.5*cm, 3*cm, 3.5*cm]
        dis_tbl = Table(rows, colWidths=col_w, repeatRows=1)
        last    = len(rows) - 1
        dis_style = TableStyle([
            *_tbl_style_base(),
            ('ALIGN',      (0, 1), (0,  -1), 'CENTER'),
            ('ALIGN',      (5, 1), (5,  -1), 'RIGHT'),
            # Total row formatting
            ('FONTNAME',   (0, last), (-1, last), 'Helvetica-Bold'),
            ('BACKGROUND', (0, last), (-1, last), PRIMARY),
            ('TEXTCOLOR',  (0, last), (-1, last), WHITE),
            ('ALIGN',      (5, last), (5,  last), 'RIGHT'),
        ])
        dis_tbl.setStyle(dis_style)
        story.append(dis_tbl)

        story.append(Spacer(1, 30))

        # ── Authorisation section ─────────────────────────────────────────
        auth_data = [
            ['Prepared By', 'Verified By', 'Approved By'],
            ['\n\n\n___________________', '\n\n\n___________________', '\n\n\n___________________'],
            ['Name & Signature',           'Name & Signature',          'Name & Signature'],
            ['Date : _______________',     'Date : _______________',    'Date : _______________'],
        ]
        auth_tbl = Table(auth_data, colWidths=[6*cm]*3, hAlign='CENTER')
        auth_tbl.setStyle(TableStyle([
            ('ALIGN',    (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR',(0, 0), (-1, 0),  PRIMARY),
            ('TOPPADDING',(0, 0),(-1,-1),  4),
            ('BOTTOMPADDING',(0, 0),(-1,-1), 4),
            ('BOX',      (0, 0), (0, -1),  0.5, GREY_LINE),
            ('BOX',      (1, 0), (1, -1),  0.5, GREY_LINE),
            ('BOX',      (2, 0), (2, -1),  0.5, GREY_LINE),
        ]))
        story.append(auth_tbl)

        story.append(Spacer(1, 20))
        story.append(HRFlowable(width='100%', thickness=0.5, color=GREY_LINE))
        story.append(Paragraph(
            'Confidential — For Internal Use Only. This is a system-generated document.',
            styles['footer']
        ))

        doc.build(story)
        buf.seek(0)
        filename = f"Salary_Disbursement_{salary_month}.pdf"
        return send_file(
            buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()

# ════════════════════════════════════════════════════════════════════════════
#  3.  INDIVIDUAL SALARY SLIP PDF
#  Add this route inside account.py  (paste after salary_disbursement_pdf)
# ════════════════════════════════════════════════════════════════════════════

@account_bp.route('/salary_slip_pdf', methods=['GET'])
@jwt_required
def salary_slip_pdf(id=None, org_id=None, role=None):
    """
    GET /salary_slip_pdf?salary_month=2026-03&user_id=<uuid>
    Returns a downloadable PDF salary slip for one employee.
    """
    salary_month = request.args.get('salary_month')
    user_id      = request.args.get('user_id')

    if not salary_month or not user_id:
        return jsonify({'status': 'error', 'message': 'salary_month and user_id are required'}), 400

    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # ── Employee info + salary record + attendance ───────────────────
        cursor.execute("""
            SELECT
                u.Name,
                u.Contact,
                ss.adj_base, ss.adj_agp, ss.adj_da, ss.adj_dp,
                ss.adj_hra, ss.adj_tra, ss.adj_cla,
                ss.pt, ss.pf, ss.other_deduction,
                ss.absent_days_deduction,
                ss.gross_salary,
                ss.net_salary,
                ss.salary_month,
                ss.salary_date
            FROM staff_salary_record ss
            JOIN users u ON ss.user_id = u.id
            WHERE ss.user_id = %s AND ss.org_id = %s AND ss.salary_month = %s
        """, (user_id, org_id, salary_month))
        rec = cursor.fetchone()

        if not rec:
            return jsonify({
                'status': 'fail',
                'message': 'No salary record found for this employee and month.'
            }), 404

        # ── Org name ─────────────────────────────────────────────────────

        # ── Date range from salary_month (YYYY-MM) ────────────────────────
        try:
            from calendar import monthrange
            yr, mo  = map(int, salary_month.split('-'))
            days_in = monthrange(yr, mo)[1]
            period_start = f"{salary_month}-01"
            period_end   = f"{salary_month}-{days_in:02d}"
            total_days   = days_in
        except Exception:
            period_start = period_end = salary_month
            total_days   = 30

        # Absent days: back-calculate from absent_days_deduction & base
        # (use the stored absent_days_deduction as a label proxy)
        absent_days  = 0
        working_days = total_days
        if rec['adj_base'] and rec['adj_base'] > 0 and rec['absent_days_deduction']:
            per_day     = rec['adj_base'] / total_days
            absent_days = round(rec['absent_days_deduction'] / per_day) if per_day else 0
            working_days = total_days - absent_days

        salary_date = str(rec['salary_date']) if rec['salary_date'] else period_end

        # ── Build PDF ────────────────────────────────────────────────────
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=1.8*cm, rightMargin=1.8*cm,
            topMargin=1.5*cm,  bottomMargin=1.5*cm
        )
        styles = _styles()
        story  = []

        org_name = "Test"
        # ── Header ───────────────────────────────────────────────────────
        story.append(Paragraph(org_name, styles['title']))
        story.append(Paragraph('SALARY SLIP', ParagraphStyle(
            'SlipTitle', fontSize=14, fontName='Helvetica-Bold',
            textColor=ACCENT, alignment=TA_CENTER, spaceBefore=2, spaceAfter=2
        )))
        story.append(Paragraph('Confidential Document', ParagraphStyle(
            'Confidential', fontSize=9, fontName='Helvetica-Oblique',
            textColor=colors.grey, alignment=TA_CENTER, spaceAfter=8
        )))
        story.append(HRFlowable(width='100%', thickness=2, color=PRIMARY, spaceAfter=10))

        # ── Employee Information block ────────────────────────────────────
        story.append(Paragraph('EMPLOYEE INFORMATION', ParagraphStyle(
            'EmpInfoHdr', fontSize=10, fontName='Helvetica-Bold',
            textColor=WHITE, backColor=PRIMARY,
            alignment=TA_LEFT, spaceBefore=0, spaceAfter=0,
            leftIndent=-4, rightIndent=-4,
            borderPad=6
        )))
        story.append(Spacer(1, 4))

        info_data = [
            [
                Paragraph('<b>Employee Name:</b>', styles['normal']),
                Paragraph(rec['Name'] or '—', styles['normal']),
                Paragraph('<b>Contact:</b>', styles['normal']),
                Paragraph(str(rec['Contact'] or '—'), styles['normal']),
            ],
            
            [
                Paragraph('', styles['normal']),
                Paragraph('', styles['normal']),
                Paragraph('<b>Salary Date:</b>', styles['normal']),
                Paragraph(str(salary_date), styles['normal']),
            ],
        ]
        info_tbl = Table(info_data, colWidths=[3.8*cm, 5.8*cm, 3*cm, 5*cm])
        info_tbl.setStyle(TableStyle([
            ('FONTSIZE',     (0, 0), (-1, -1), 9),
            ('TOPPADDING',   (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
            ('LEFTPADDING',  (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('BACKGROUND',   (0, 0), (-1, -1), LIGHT_BG),
            ('GRID',         (0, 0), (-1, -1), 0.4, GREY_LINE),
            ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(info_tbl)
        story.append(Spacer(1, 8))

        # ── Attendance row ───────────────────────────────────────────────
        att_data = [[
            Paragraph(f'<b>Total Days:</b> {total_days}',    styles['normal']),
            Paragraph(f'<b>Working Days:</b> {working_days}', styles['normal']),
            Paragraph(f'<b>Absent Days:</b> {absent_days}',  styles['normal']),
        ]]
        att_tbl = Table(att_data, colWidths=[6*cm, 6*cm, 6*cm])
        att_tbl.setStyle(TableStyle([
            ('FONTSIZE',     (0, 0), (-1, -1), 9),
            ('TOPPADDING',   (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
            ('LEFTPADDING',  (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND',   (0, 0), (-1, -1), ALT_ROW),
            ('GRID',         (0, 0), (-1, -1), 0.4, GREY_LINE),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(att_tbl)
        story.append(Spacer(1, 6))

        # ── Gross Salary Banner ──────────────────────────────────────────
        gross_banner = [[
            Paragraph(
                f'<b>GROSS SALARY (Before Adjustments): {_currency(rec["gross_salary"])}</b>',
                ParagraphStyle('GrossBanner', fontSize=10, fontName='Helvetica-Bold',
                               textColor=WHITE, alignment=TA_CENTER)
            )
        ]]
        gross_tbl = Table(gross_banner, colWidths=[17.4*cm])
        gross_tbl.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, -1), PRIMARY),
            ('TOPPADDING',   (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 8),
        ]))
        story.append(gross_tbl)
        story.append(Spacer(1, 6))

        # ── Earnings | Deductions split table ────────────────────────────
        earn_header = Paragraph('<b>EARNINGS (After Adjustment)</b>', ParagraphStyle(
            'EH', fontSize=9, fontName='Helvetica-Bold', textColor=WHITE))
        ded_header  = Paragraph('<b>DEDUCTIONS</b>', ParagraphStyle(
            'DH', fontSize=9, fontName='Helvetica-Bold', textColor=WHITE))

        def _earn(label, val):
            return [
                Paragraph(label, styles['normal']),
                Paragraph(_currency(val), ParagraphStyle(
                    'EV', fontSize=9, fontName='Helvetica', textColor=GREEN, alignment=TA_RIGHT))
            ]

        def _ded(label, val):
            return [
                Paragraph(label, styles['normal']),
                Paragraph(_currency(val), ParagraphStyle(
                    'DV', fontSize=9, fontName='Helvetica', textColor=RED, alignment=TA_RIGHT))
            ]

        earn_rows = [
            _earn('Adjusted Base Salary', rec['adj_base']),
            _earn('Adjusted AGP',         rec['adj_agp']),
            _earn('Adjusted DA',          rec['adj_da']),
            _earn('Adjusted DP',          rec['adj_dp']),
            _earn('Adjusted HRA',         rec['adj_hra']),
            _earn('Adjusted TRA',         rec['adj_tra']),
            _earn('Adjusted CLA',         rec['adj_cla']),
        ]
        ded_rows = [
            _ded('Provident Fund (PF)',  rec['pf']),
            _ded('Professional Tax (PT)', rec['pt']),
            _ded('Other Deductions',     rec['other_deduction']),
        ]

        # Pad shorter side so both columns have equal rows
        blank_earn = [Paragraph('', styles['normal']), Paragraph('', styles['normal'])]
        blank_ded  = [Paragraph('', styles['normal']), Paragraph('', styles['normal'])]
        max_rows   = max(len(earn_rows), len(ded_rows))
        while len(earn_rows) < max_rows: earn_rows.append(blank_earn)
        while len(ded_rows)  < max_rows: ded_rows.append(blank_ded)

        # Build combined table: [earn_label | earn_val | gap | ded_label | ded_val]
        ed_data  = [[earn_header, '', '', ded_header, '']]
        for e, d in zip(earn_rows, ded_rows):
            ed_data.append([e[0], e[1], '', d[0], d[1]])

        total_row = [
            Paragraph('<b>TOTAL EARNINGS:</b>', ParagraphStyle('TE', fontSize=9, fontName='Helvetica-Bold', textColor=GREEN)),
            Paragraph(_currency(rec['gross_salary']), ParagraphStyle('TEV', fontSize=9, fontName='Helvetica-Bold', textColor=GREEN, alignment=TA_RIGHT)),
            '',
            Paragraph('<b>TOTAL DEDUCTIONS:</b>', ParagraphStyle('TD', fontSize=9, fontName='Helvetica-Bold', textColor=RED)),
            Paragraph(_currency(rec['pf'] + rec['pt'] + rec['other_deduction'] + rec['absent_days_deduction']),
                      ParagraphStyle('TDV', fontSize=9, fontName='Helvetica-Bold', textColor=RED, alignment=TA_RIGHT)),
        ]
        ed_data.append(total_row)

        last_r = len(ed_data) - 1
        ed_tbl = Table(ed_data, colWidths=[4.8*cm, 3.2*cm, 0.4*cm, 5.6*cm, 3.4*cm])
        ed_tbl.setStyle(TableStyle([
            # Header row
            ('BACKGROUND',   (0, 0), (1, 0),  PRIMARY),
            ('BACKGROUND',   (3, 0), (4, 0),  PRIMARY),
            ('SPAN',         (0, 0), (1, 0)),
            ('SPAN',         (3, 0), (4, 0)),
            ('ALIGN',        (0, 0), (1, 0),  'CENTER'),
            ('ALIGN',        (3, 0), (4, 0),  'CENTER'),
            ('TOPPADDING',   (0, 0), (-1, 0),  7),
            ('BOTTOMPADDING',(0, 0), (-1, 0),  7),
            # Data rows
            ('FONTSIZE',     (0, 1), (-1, -1), 9),
            ('TOPPADDING',   (0, 1), (-1, -2), 5),
            ('BOTTOMPADDING',(0, 1), (-1, -2), 5),
            ('LEFTPADDING',  (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUND',(0, 1), (-1, -2), [WHITE, ALT_ROW]),
            ('GRID',         (0, 0), (1, -1),  0.4, GREY_LINE),
            ('GRID',         (3, 0), (4, -1),  0.4, GREY_LINE),
            # Gap column — no borders
            ('BACKGROUND',   (2, 0), (2, -1), WHITE),
            ('GRID',         (2, 0), (2, -1), 0, WHITE),
            # Total row
            ('BACKGROUND',   (0, last_r), (1, last_r), LIGHT_BG),
            ('BACKGROUND',   (3, last_r), (4, last_r), LIGHT_BG),
            ('TOPPADDING',   (0, last_r), (-1, last_r), 7),
            ('BOTTOMPADDING',(0, last_r), (-1, last_r), 7),
            ('LINEABOVE',    (0, last_r), (1, last_r), 1, PRIMARY),
            ('LINEABOVE',    (3, last_r), (4, last_r), 1, PRIMARY),
            ('ALIGN',        (1, last_r), (1, last_r), 'RIGHT'),
            ('ALIGN',        (4, last_r), (4, last_r), 'RIGHT'),
        ]))
        story.append(ed_tbl)
        story.append(Spacer(1, 10))

        # ── Net Salary Banner ────────────────────────────────────────────
        net_banner = [[
            Paragraph(
                f'<b>NET SALARY: {_currency(rec["net_salary"])}</b>',
                ParagraphStyle('NetBanner', fontSize=13, fontName='Helvetica-Bold',
                               textColor=WHITE, alignment=TA_CENTER)
            )
        ]]
        net_tbl = Table(net_banner, colWidths=[17.4*cm])
        net_tbl.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, -1), GREEN),
            ('TOPPADDING',   (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 10),
            ('ROUNDEDCORNERS', [6]),
        ]))
        story.append(net_tbl)
        story.append(Spacer(1, 18))

        # ── Footer notes ─────────────────────────────────────────────────
        notes = [
            '• This is a system-generated salary slip and does not require a signature.',
            '• For any queries regarding this salary slip, please contact the HR department.',
            f'• Generated on: {datetime.now().strftime("%Y-%m-%d")}',
        ]
        for note in notes:
            story.append(Paragraph(note, ParagraphStyle(
                'Note', fontSize=8, fontName='Helvetica-Oblique',
                textColor=colors.grey, spaceAfter=3
            )))

        story.append(Spacer(1, 10))
        story.append(HRFlowable(width='100%', thickness=0.5, color=GREY_LINE))
        story.append(Paragraph(
            'Confidential — For Internal Use Only.',
            styles['footer']
        ))

        doc.build(story)
        buf.seek(0)

        safe_name = (rec['Name'] or 'Employee').replace(' ', '_')
        filename  = f"SalarySlip_{safe_name}_{salary_month}.pdf"
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()