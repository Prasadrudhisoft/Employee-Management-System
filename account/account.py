from flask import request, jsonify, Blueprint, send_file
import pymysql
from connector import get_connection
from decorators import jwt_required
import uuid, io

from datetime import datetime
from calendar import monthrange

# ── ReportLab ──────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

account_bp = Blueprint('account', __name__)


# ════════════════════════════════════════════════════════════════════════════
#  SHARED COLOUR PALETTE
# ════════════════════════════════════════════════════════════════════════════
# -- Summary / Slip colours
PRIMARY    = colors.HexColor("#ADADAD")
ACCENT     = colors.HexColor('#2e86c1')
GREEN      = colors.HexColor('#27ae60')
RED        = colors.HexColor('#c0392b')
WHITE      = colors.white
LIGHT_BG   = colors.HexColor('#eaf0f8')
ALT_ROW    = colors.HexColor('#f4f7fb')
GREY_LINE  = colors.HexColor('#c8d4e0')

# -- Disbursement-specific colours (richer design)
D_DARK       = colors.HexColor('#1a1a2e')
D_TABLE_HEAD = colors.HexColor('#0f3460')
D_ROW_ALT    = colors.HexColor('#f0f4ff')
D_DIVIDER    = colors.HexColor('#c8d0e0')
D_GREEN      = colors.HexColor('#1a6644')
D_LIGHT_TEXT = colors.HexColor('#4a5568')
D_INK        = colors.HexColor('#1a202c')


# ════════════════════════════════════════════════════════════════════════════
#  SHARED HELPERS
# ════════════════════════════════════════════════════════════════════════════
def _currency(val):
    if val is None:
        return '₹0.00'
    try:
        return f'₹{float(val):,.2f}'
    except Exception:
        return f'₹{val}'


def _styles():
    """Single merged style dictionary used by Summary and Salary-Slip PDF routes."""
    return {
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
        'bold_right': ParagraphStyle(
            'BoldRight', fontSize=9, fontName='Helvetica-Bold',
            textColor=PRIMARY, alignment=TA_RIGHT
        ),
        'normal': ParagraphStyle(
            'normal', fontSize=9, fontName='Helvetica',
            textColor=colors.HexColor('#2c3e50'), leading=12
        ),
        'footer': ParagraphStyle(
            'footer', fontSize=8, fontName='Helvetica-Oblique',
            textColor=colors.grey, alignment=TA_CENTER, spaceBefore=4
        ),
    }


def _header_block(story, styles, title_text, salary_month, org_name=None):
    """Common header used by Summary PDF."""
    story.append(Paragraph(title_text, styles['title']))
    if org_name:
        story.append(Paragraph(org_name, styles['subtitle']))
    story.append(Paragraph(f"Salary Month : {salary_month}", styles['meta']))
    story.append(Paragraph(
        f"Generated on : {datetime.now().strftime('%d %B %Y, %I:%M %p')}",
        styles['meta']
    ))
    story.append(HRFlowable(width='100%', thickness=1.5, color=ACCENT, spaceAfter=10))


def _tbl_style_base():
    return [
        ('BACKGROUND',    (0, 0), (-1, 0),  PRIMARY),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  WHITE),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0),  9),
        ('ALIGN',         (0, 0), (-1, 0),  'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0),  8),
        ('TOPPADDING',    (0, 0), (-1, 0),  8),
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -1), 8.5),
        ('ROWBACKGROUND', (0, 1), (-1, -1), [WHITE, ALT_ROW]),
        ('GRID',          (0, 0), (-1, -1), 0.4, GREY_LINE),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
    ]


# ════════════════════════════════════════════════════════════════════════════
#  ROUTES – DATA ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════

@account_bp.route('/get_salary_details', methods=['GET'])
@jwt_required
def get_salary_detailes(id=None, role=None, org_id=None, org_name=None):
    try:
        conn   = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute(
            "SELECT u.Name, s.user_id, s.base_salary, s.agp, s.da, s.dp, "
            "s.hra, s.tra, s.cla "
            "FROM users u "
            "INNER JOIN salary_detailes s ON u.id = s.user_id "
            "WHERE u.status = 'Active' AND s.org_id = %s",
            (org_id,)
        )
        emp = cursor.fetchall()
        return jsonify({
            'status': 'success',
            'message': 'salary records fetched successfully.',
            'emp': emp
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


@account_bp.route('/get_monthly_salary_records', methods=['GET'])
@jwt_required
def get_monthly_salary_records(id=None, role=None, org_id=None, org_name=None):
    try:
        conn   = get_connection()
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
        return jsonify({'status': 'success', 'records': records})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


@account_bp.route('/emp_salary', methods=['GET', 'POST'])
@jwt_required
def emp_salary(id=None, org_id=None, role=None, org_name=None):
    try:
        conn   = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        data                  = request.json
        salary_month          = data.get('salary_month')
        salary_date           = data.get('salary_date')
        sal_record            = str(uuid.uuid4())
        user_id               = data.get('user_id')
        base_salary           = float(data.get('base_salary', 0))
        agp                   = float(data.get('agp', 0))
        da                    = float(data.get('da', 0))
        dp                    = float(data.get('dp', 0))
        hra                   = float(data.get('hra', 0))
        tra                   = float(data.get('tra', 0))
        cla                   = float(data.get('cla', 0))
        pt                    = float(data.get('pt', 0))
        pf                    = float(data.get('pf', 0))
        other_deduction       = float(data.get('other_deduction', 0))
        absent_days_deduction = float(data.get('absent_days_deduction', 0))
        gross_salary = base_salary + agp + da + dp + hra + tra + cla
        net_salary   = gross_salary - (pf + pt + other_deduction + absent_days_deduction)
        cursor.execute(
            "SELECT id FROM staff_salary_record "
            "WHERE user_id = %s AND org_id = %s AND salary_month = %s",
            (user_id, org_id, salary_month)
        )
        if cursor.fetchone():
            return jsonify({'status': 'fail', 'message': 'Salary Already Recorded For This Employee'})
        cursor.execute(
            "INSERT INTO staff_salary_record "
            "(id,user_id,org_id,adj_base,adj_agp,adj_da,adj_dp,adj_hra,adj_tra,adj_cla,"
            " pt,pf,other_deduction,absent_days_deduction,gross_salary,net_salary,"
            " salary_month,salary_date,created_by,created_date) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())",
            (sal_record, user_id, org_id, base_salary, agp, da, dp, hra, tra, cla,
             pt, pf, other_deduction, absent_days_deduction,
             gross_salary, net_salary, salary_month, salary_date, id)
        )
        conn.commit()
        return jsonify({'status': 'success',
                        'message': f'{salary_month} Months Salary Recorded Successfully.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


@account_bp.route('/update_emp_salary', methods=['PUT'])
@jwt_required
def update_emp_salary(id=None, org_id=None, role=None, org_name=None):
    try:
        conn   = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        data         = request.json
        user_id      = data.get('user_id')
        salary_month = data.get('salary_month')
        if not user_id or not salary_month:
            return jsonify({'status': 'error',
                            'message': 'user_id and salary_month are required'}), 400
        cursor.execute(
            "SELECT id FROM staff_salary_record "
            "WHERE user_id = %s AND org_id = %s AND salary_month = %s",
            (user_id, org_id, salary_month)
        )
        if not cursor.fetchone():
            return jsonify({
                'status': 'fail',
                'message': 'No saved record found for this employee and month. Save first before updating.'
            })
        base_salary           = data.get('base_salary', 0)
        agp                   = data.get('agp', 0)
        da                    = data.get('da', 0)
        dp                    = data.get('dp', 0)
        hra                   = data.get('hra', 0)
        tra                   = data.get('tra', 0)
        cla                   = data.get('cla', 0)
        pt                    = data.get('pt', 0)
        pf                    = data.get('pf', 0)
        other_deduction       = data.get('other_deduction', 0)
        absent_days_deduction = data.get('absent_days_deduction', 0)
        gross_salary = base_salary + agp + da + dp + hra + tra + cla
        net_salary   = gross_salary - (pf + pt + other_deduction + absent_days_deduction)
        cursor.execute(
            "UPDATE staff_salary_record SET "
            "adj_base=%s,adj_agp=%s,adj_da=%s,adj_dp=%s,adj_hra=%s,adj_tra=%s,adj_cla=%s,"
            "pt=%s,pf=%s,other_deduction=%s,absent_days_deduction=%s,"
            "gross_salary=%s,net_salary=%s "
            "WHERE user_id=%s AND org_id=%s AND salary_month=%s",
            (base_salary, agp, da, dp, hra, tra, cla,
             pt, pf, other_deduction, absent_days_deduction,
             gross_salary, net_salary,
             user_id, org_id, salary_month)
        )
        conn.commit()
        return jsonify({'status': 'success',
                        'message': f'Salary updated successfully for {salary_month}.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


@account_bp.route('/salary_summary', methods=['GET'])
@jwt_required
def salary_summary(id=None, org_id=None, role=None, org_name=None):
    try:
        conn   = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        salary_month = request.args.get('salary_month')
        if not salary_month:
            return jsonify({'status': 'fail',
                            'message': 'Salary Records Not Found For Selected Month'})
        cursor.execute(
            "SELECT COUNT(user_id) AS total_emp,"
            " SUM(adj_base) AS base, SUM(adj_agp) AS agp, SUM(adj_da) AS da,"
            " SUM(adj_dp) AS dp, SUM(adj_hra) AS hra, SUM(adj_tra) AS tra, SUM(adj_cla) AS cla,"
            " SUM(pt) AS pt, SUM(pf) AS pf,"
            " SUM(other_deduction) AS other_deduction,"
            " SUM(absent_days_deduction) AS absent_days_deduction,"
            " SUM(net_salary) AS net_salary,"
            " (SUM(adj_base)+SUM(adj_agp)+SUM(adj_da)+SUM(adj_dp)+"
            "  SUM(adj_hra)+SUM(adj_tra)+SUM(adj_cla)) AS earnings,"
            " (SUM(pt)+SUM(pf)+SUM(other_deduction)+SUM(absent_days_deduction)) AS deductions"
            " FROM staff_salary_record"
            " WHERE org_id = %s AND salary_month = %s",
            (org_id, salary_month)
        )
        summary = cursor.fetchone()
        return jsonify({'status': 'success', 'message': 'All Salary Summary Loaded',
                        'summary': summary})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


@account_bp.route('/salary_disbursement', methods=['GET'])
@jwt_required
def salary_disbursement(id=None, org_id=None, role=None, org_name=None):
    try:
        conn   = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        salary_month = request.args.get('salary_month')
        if not salary_month:
            return jsonify({'status': 'fail',
                            'message': 'Month Selected have no salary detailes'})
        cursor.execute(
            "SELECT u.id AS user_id, u.Name, sd.bank_acc_no, sd.ifsc_code, sd.bank_name, ss.net_salary"
            " FROM users u"
            " JOIN salary_detailes sd ON u.id = sd.user_id"
            " JOIN staff_salary_record ss ON u.id = ss.user_id"
            " WHERE ss.org_id = %s AND ss.salary_month = %s",
            (org_id, salary_month)
        )
        users = cursor.fetchall()
        return jsonify({
            'status': 'success',
            'message': f'All Salary Records For Selected Month {salary_month} fetched successfully.',
            'users': users
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


# ════════════════════════════════════════════════════════════════════════════
#  1.  SALARY SUMMARY PDF
# ════════════════════════════════════════════════════════════════════════════
@account_bp.route('/salary_summary_pdf', methods=['GET'])
@jwt_required
def salary_summary_pdf(id=None, org_id=None, role=None, org_name=None):
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
                COUNT(user_id)                                                AS total_employees,
                SUM(adj_base)                                                 AS base,
                SUM(adj_agp)                                                  AS agp,
                SUM(adj_da)                                                   AS da,
                SUM(adj_dp)                                                   AS dp,
                SUM(adj_hra)                                                  AS hra,
                SUM(adj_tra)                                                  AS tra,
                SUM(adj_cla)                                                  AS cla,
                SUM(adj_base+adj_agp+adj_da+adj_dp+adj_hra+adj_tra+adj_cla)  AS gross_salary,
                SUM(pt)                                                       AS pt,
                SUM(pf)                                                       AS pf,
                SUM(other_deduction)                                          AS other_deduction,
                SUM(absent_days_deduction)                                    AS absent_days_deduction,
                SUM(pt+pf+other_deduction+absent_days_deduction)             AS total_deductions,
                SUM(net_salary)                                               AS net_salary
            FROM staff_salary_record
            WHERE org_id = %s AND salary_month = %s
        """, (org_id, salary_month))
        s = cursor.fetchone()

        if not s or s['total_employees'] == 0:
            return jsonify({'status': 'fail',
                            'message': 'No salary records found for the selected month.'}), 404

        buf    = io.BytesIO()
        doc    = SimpleDocTemplate(
            buf, pagesize=landscape(A4),
            leftMargin=1.5*cm, rightMargin=1.5*cm,
            topMargin=1.5*cm,  bottomMargin=1.5*cm
        )
        styles = _styles()
        story  = []

        _header_block(story, styles, 'Salary Summary Report', salary_month)

        story.append(Paragraph('Organisation Summary', styles['section']))
        kpi_data = [
            ['Total Employees', 'Total Gross', 'Total Deductions', 'Total Net Payable'],
            [str(int(s['total_employees'] or 0)),
             _currency(s['gross_salary']),
             _currency(s['total_deductions']),
             _currency(s['net_salary'])]
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
            ('SPAN',       (2, 0),    (2, last)),
            ('BACKGROUND', (2, 0),    (2, last),  WHITE),
            ('GRID',       (2, 0),    (2, last),  0, WHITE),
            ('FONTNAME',   (0, last), (-1, last), 'Helvetica-Bold'),
            ('BACKGROUND', (0, last), (1,  last), LIGHT_BG),
            ('BACKGROUND', (3, last), (4,  last), LIGHT_BG),
            ('TEXTCOLOR',  (0, last), (1,  last), GREEN),
            ('TEXTCOLOR',  (3, last), (4,  last), RED),
            ('ALIGN',      (1, 1),    (1,  last), 'RIGHT'),
            ('ALIGN',      (4, 1),    (4,  last), 'RIGHT'),
        ]))
        story.append(bd_tbl)
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width='100%', thickness=0.5, color=GREY_LINE))
        story.append(Paragraph(
            'This is a system-generated report. No signature is required.',
            styles['footer']
        ))

        doc.build(story)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', as_attachment=True,
                         download_name=f"Salary_Summary_{salary_month}.pdf")

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ════════════════════════════════════════════════════════════════════════════
#  2.  SALARY DISBURSEMENT PDF  ── polished design matching sample
# ════════════════════════════════════════════════════════════════════════════
@account_bp.route('/salary_disbursement_pdf', methods=['GET'])
@jwt_required
def salary_disbursement_pdf(id=None, org_id=None, role=None, org_name=None):
    salary_month = request.args.get('salary_month')
    if not salary_month:
        return jsonify({'status': 'error', 'message': 'salary_month is required'}), 400

    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute("""
            SELECT u.Name, sd.bank_acc_no, sd.ifsc_code, sd.bank_name, ss.net_salary
            FROM users u
            JOIN salary_detailes sd ON u.id = sd.user_id
            JOIN staff_salary_record ss ON u.id = ss.user_id
            WHERE ss.org_id = %s AND ss.salary_month = %s
            ORDER BY u.Name
        """, (org_id, salary_month))
        employees = cursor.fetchall()

        if not employees:
            return jsonify({'status': 'fail',
                            'message': 'No disbursement records found for the selected month.'}), 404

        total_net = sum(float(e['net_salary'] or 0) for e in employees)

        # ── page setup ───────────────────────────────────────────────────
        buf       = io.BytesIO()
        PAGE_W    = A4[0]
        CONTENT_W = PAGE_W - 3.6*cm   # margins 1.8 each side

        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=1.8*cm, rightMargin=1.8*cm,
            topMargin=0,        bottomMargin=1.5*cm,
        )
        story = []

        # ── period string ────────────────────────────────────────────────
        try:
            yr, mo = map(int, salary_month.split('-'))
            days   = monthrange(yr, mo)[1]
            period = f"{salary_month}-01 to {salary_month}-{days:02d}"
        except Exception:
            period = salary_month

        def _ps(name, **kw):
            return ParagraphStyle(name, **kw)

        # ── HEADER BANNER ────────────────────────────────────────────────
        hdr_data = [
            [Paragraph("Salary Disbursement Report",
                       _ps('HT', fontSize=20, fontName='Helvetica-Bold',
                           textColor=WHITE, alignment=TA_CENTER,
                           spaceBefore=0, spaceAfter=0, leading=26))],
            [Paragraph(f"Period: {period}",
                       _ps('HS', fontSize=10, fontName='Helvetica',
                           textColor=colors.HexColor('#a0b4d0'), alignment=TA_CENTER,
                           spaceBefore=0, spaceAfter=0, leading=14))],
            [Paragraph(f"Generated on: {datetime.now().strftime('%d %B %Y, %I:%M %p')}",
                       _ps('HG', fontSize=8, fontName='Helvetica',
                           textColor=colors.HexColor('#7090a8'), alignment=TA_CENTER,
                           spaceBefore=0, spaceAfter=0, leading=12))],
        ]
        hdr_tbl = Table(hdr_data, colWidths=[CONTENT_W])
        hdr_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), D_DARK),
            ('TOPPADDING',    (0,0), (0,0),   22),
            ('BOTTOMPADDING', (0,0), (0,0),   4),
            ('TOPPADDING',    (0,1), (0,1),   2),
            ('BOTTOMPADDING', (0,1), (0,1),   2),
            ('TOPPADDING',    (0,2), (0,2),   2),
            ('BOTTOMPADDING', (0,2), (0,2),   18),
            ('LEFTPADDING',   (0,0), (-1,-1), 12),
            ('RIGHTPADDING',  (0,0), (-1,-1), 12),
        ]))
        story.append(hdr_tbl)
        story.append(Spacer(1, 18))

        # ── SUMMARY CARDS ────────────────────────────────────────────────
        card_w = (CONTENT_W - 0.6*cm) / 2

        def _summary_card(label, value, val_color=D_INK):
            inner = Table(
                [[Paragraph(label, _ps('CL', fontSize=8, fontName='Helvetica-Bold',
                                       textColor=D_LIGHT_TEXT, alignment=TA_LEFT,
                                       spaceBefore=0, spaceAfter=4, leading=10))],
                 [Paragraph(value, _ps('CV', fontSize=15, fontName='Helvetica-Bold',
                                       textColor=val_color, alignment=TA_LEFT,
                                       spaceBefore=0, spaceAfter=0, leading=18))]],
                colWidths=[card_w - 1.4*cm]
            )
            wrap = Table([[inner]], colWidths=[card_w])
            wrap.setStyle(TableStyle([
                ('BACKGROUND',    (0,0), (-1,-1), WHITE),
                ('BOX',           (0,0), (-1,-1), 0.8, D_DIVIDER),
                ('TOPPADDING',    (0,0), (-1,-1), 14),
                ('BOTTOMPADDING', (0,0), (-1,-1), 14),
                ('LEFTPADDING',   (0,0), (-1,-1), 16),
                ('RIGHTPADDING',  (0,0), (-1,-1), 16),
            ]))
            return wrap

        cards = Table(
            [[_summary_card("TOTAL EMPLOYEES",          str(len(employees))),
              _summary_card("TOTAL AMOUNT TO DISBURSE", _currency(total_net), D_GREEN)]],
            colWidths=[card_w, card_w]
        )
        cards.setStyle(TableStyle([
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ('TOPPADDING',    (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(cards)
        story.append(Spacer(1, 20))

        # ── SECTION HEADING ──────────────────────────────────────────────
        story.append(Paragraph(
            "Employee Bank Details &amp; Net Payable",
            _ps('SH', fontSize=12, fontName='Helvetica-Bold',
                textColor=D_INK, spaceBefore=0, spaceAfter=8, leading=16)
        ))

        # ── MAIN TABLE ───────────────────────────────────────────────────
        col_w = [0.8*cm, 4.4*cm, 3.2*cm, 3.8*cm, 3.0*cm, 3.2*cm]

        def _th(t):
            return Paragraph(t, _ps('TH', fontSize=8, fontName='Helvetica-Bold',
                                    textColor=WHITE, alignment=TA_CENTER,
                                    spaceBefore=0, spaceAfter=0, leading=11))

        def _td(t, align=TA_LEFT, bold=False, color=D_INK):
            return Paragraph(t, _ps('TD', fontSize=8.5,
                                    fontName='Helvetica-Bold' if bold else 'Helvetica',
                                    textColor=color, alignment=align,
                                    spaceBefore=0, spaceAfter=0, leading=12))

        rows = [[_th('#'), _th('Employee Name'), _th('Bank Name'),
                 _th('Account Number'), _th('IFSC Code'), _th('Net Salary')]]

        for i, e in enumerate(employees, 1):
            rows.append([
                _td(str(i),                  TA_CENTER),
                _td(e['Name']          or '—'),
                _td(e['bank_name']     or '—'),
                _td(e['bank_acc_no']   or '—', TA_CENTER),
                _td(e['ifsc_code']     or '—', TA_CENTER),
                _td(_currency(e['net_salary']), TA_RIGHT, bold=True, color=D_GREEN),
            ])

        rows.append([
            _td('',       TA_CENTER),
            _td('TOTAL',  TA_LEFT,  bold=True, color=WHITE),
            _td('',       TA_CENTER),
            _td('',       TA_CENTER),
            _td('',       TA_CENTER),
            _td(_currency(total_net), TA_RIGHT, bold=True, color=WHITE),
        ])

        last   = len(rows) - 1
        main_t = Table(rows, colWidths=col_w, repeatRows=1)
        main_t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0),     (-1, 0),      D_TABLE_HEAD),
            ('TOPPADDING',    (0, 0),     (-1, 0),      10),
            ('BOTTOMPADDING', (0, 0),     (-1, 0),      10),
            ('TOPPADDING',    (0, 1),     (-1, last-1), 8),
            ('BOTTOMPADDING', (0, 1),     (-1, last-1), 8),
            ('ROWBACKGROUNDS',(0, 1),     (-1, last-1), [WHITE, D_ROW_ALT]),
            ('LINEBELOW',     (0, 0),     (-1, last-1), 0.4, D_DIVIDER),
            ('LINEAFTER',     (0, 0),     (-2, -1),     0.4, D_DIVIDER),
            ('BACKGROUND',    (0, last),  (-1, last),   D_TABLE_HEAD),
            ('TOPPADDING',    (0, last),  (-1, last),   10),
            ('BOTTOMPADDING', (0, last),  (-1, last),   10),
            ('BOX',           (0, 0),     (-1, -1),     0.8, colors.HexColor('#9aaabf')),
            ('VALIGN',        (0, 0),     (-1, -1),     'MIDDLE'),
            ('LEFTPADDING',   (0, 0),     (-1, -1),     8),
            ('RIGHTPADDING',  (0, 0),     (-1, -1),     8),
        ]))
        story.append(main_t)
        story.append(Spacer(1, 28))

        # ── AUTHORISATION SECTION ────────────────────────────────────────
        story.append(Paragraph(
            "Authorisation",
            _ps('AH', fontSize=11, fontName='Helvetica-Bold',
                textColor=D_INK, spaceBefore=0, spaceAfter=10, leading=14)
        ))

        auth_col_w = (CONTENT_W - 0.8*cm) / 3

        def _auth_card(role_label):
            inner = Table(
                [[Paragraph(role_label,
                             _ps('AR', fontSize=9, fontName='Helvetica-Bold',
                                 textColor=D_DARK, alignment=TA_CENTER,
                                 spaceBefore=0, spaceAfter=0, leading=12))],
                 [Spacer(1, 30)],
                 [Paragraph('___________________________',
                             _ps('AL', fontSize=9, fontName='Helvetica',
                                 textColor=D_LIGHT_TEXT, alignment=TA_CENTER,
                                 spaceBefore=0, spaceAfter=0, leading=12))],
                 [Paragraph('Name &amp; Signature',
                             _ps('AS', fontSize=8, fontName='Helvetica',
                                 textColor=D_LIGHT_TEXT, alignment=TA_CENTER,
                                 spaceBefore=0, spaceAfter=2, leading=10))],
                 [Paragraph('Date: _______________',
                             _ps('AD', fontSize=8, fontName='Helvetica',
                                 textColor=D_LIGHT_TEXT, alignment=TA_CENTER,
                                 spaceBefore=0, spaceAfter=0, leading=10))],
                ],
                colWidths=[auth_col_w - 1.0*cm]
            )
            wrap = Table([[inner]], colWidths=[auth_col_w])
            wrap.setStyle(TableStyle([
                ('BACKGROUND',    (0,0), (-1,-1), WHITE),
                ('BOX',           (0,0), (-1,-1), 0.8, D_DIVIDER),
                ('TOPPADDING',    (0,0), (-1,-1), 14),
                ('BOTTOMPADDING', (0,0), (-1,-1), 14),
                ('LEFTPADDING',   (0,0), (-1,-1), 14),
                ('RIGHTPADDING',  (0,0), (-1,-1), 14),
            ]))
            return wrap

        auth_tbl = Table(
            [[_auth_card("Prepared By"),
              _auth_card("Verified By"),
              _auth_card("Approved By")]],
            colWidths=[auth_col_w, auth_col_w, auth_col_w]
        )
        auth_tbl.setStyle(TableStyle([
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ('TOPPADDING',    (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(auth_tbl)
        story.append(Spacer(1, 20))

        # ── FOOTER ───────────────────────────────────────────────────────
        story.append(HRFlowable(width='100%', thickness=0.6, color=D_DIVIDER, spaceAfter=8))
        story.append(Paragraph(
            "Confidential \u2014 For Internal Use Only  |  This is a system-generated document.",
            _ps('FT', fontSize=8, fontName='Helvetica',
                textColor=D_LIGHT_TEXT, alignment=TA_CENTER,
                spaceBefore=0, spaceAfter=0, leading=11)
        ))

        doc.build(story)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', as_attachment=True,
                         download_name=f"Salary_Disbursement_{salary_month}.pdf")

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ════════════════════════════════════════════════════════════════════════════
#  3.  INDIVIDUAL SALARY SLIP PDF
# ════════════════════════════════════════════════════════════════════════════
@account_bp.route('/salary_slip_pdf', methods=['GET'])
@jwt_required
def salary_slip_pdf(id=None, org_id=None, role=None, org_name=None):
    salary_month = request.args.get('salary_month')
    user_id      = request.args.get('user_id')

    if not salary_month or not user_id:
        return jsonify({'status': 'error',
                        'message': 'salary_month and user_id are required'}), 400

    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute("""
            SELECT u.Name, u.Contact, u.org_name,
                   ss.adj_base, ss.adj_agp, ss.adj_da, ss.adj_dp,
                   ss.adj_hra, ss.adj_tra, ss.adj_cla,
                   ss.pt, ss.pf, ss.other_deduction,
                   ss.absent_days_deduction,
                   ss.gross_salary, ss.net_salary,
                   ss.salary_month, ss.salary_date
            FROM staff_salary_record ss
            JOIN users u ON ss.user_id = u.id
            WHERE ss.user_id = %s AND ss.org_id = %s AND ss.salary_month = %s
        """, (user_id, org_id, salary_month))
        rec = cursor.fetchone()

        if not rec:
            return jsonify({'status': 'fail',
                            'message': 'No salary record found for this employee and month.'}), 404

        yr, mo       = map(int, salary_month.split('-'))
        days_in      = monthrange(yr, mo)[1]
        period_start = f"{salary_month}-01"
        period_end   = f"{salary_month}-{days_in:02d}"
        total_days   = days_in

        absent_days  = 0
        working_days = total_days
        if rec['adj_base'] and rec['adj_base'] > 0 and rec['absent_days_deduction']:
            per_day      = rec['adj_base'] / total_days
            absent_days  = round(rec['absent_days_deduction'] / per_day) if per_day else 0
            working_days = total_days - absent_days

        salary_date = str(rec['salary_date']) if rec['salary_date'] else period_end
        slip_org    = str(rec['org_name']) if rec['org_name'] else ''

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=1.8*cm, rightMargin=1.8*cm,
            topMargin=1.5*cm,  bottomMargin=1.5*cm
        )
        styles = _styles()
        story  = []
        N      = styles['normal']

        for text, fs, tp, pb in [
            (slip_org,               16, 12, 10),
            ('SALARY SLIP',          13,  2,  6),
            ('Confidential Document', 9,  2, 10),
        ]:
            is_italic = text == 'Confidential Document'
            hdr_tbl = Table([[
                Paragraph(text, ParagraphStyle(
                    f'H{fs}', fontSize=fs,
                    fontName='Helvetica-BoldOblique' if is_italic else 'Helvetica-Bold',
                    textColor=WHITE, alignment=TA_CENTER,
                    spaceBefore=0, spaceAfter=0, leading=fs + 4,
                ))
            ]], colWidths=[17.4*cm])
            hdr_tbl.setStyle(TableStyle([
                ('BACKGROUND',    (0,0), (-1,-1), PRIMARY),
                ('TOPPADDING',    (0,0), (-1,-1), tp),
                ('BOTTOMPADDING', (0,0), (-1,-1), pb),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
                ('RIGHTPADDING',  (0,0), (-1,-1), 8),
            ]))
            story.append(hdr_tbl)

        emp_hdr = Table([[
            Paragraph('EMPLOYEE INFORMATION', ParagraphStyle(
                'EmpHdr', fontSize=10, fontName='Helvetica-Bold',
                textColor=WHITE, alignment=TA_LEFT,
                spaceBefore=0, spaceAfter=0
            ))
        ]], colWidths=[17.4*cm])
        emp_hdr.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), PRIMARY),
            ('TOPPADDING',    (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 8),
        ]))
        story.append(emp_hdr)

        def _lbl(t): return Paragraph(f'<b>{t}</b>', N)
        def _val(t): return Paragraph(str(t or '—'), N)

        info_data = [
            [_lbl('Employee Name:'), _val(rec['Name']),
             _lbl('Contact:'),       _val(rec['Contact'])],
            [_lbl('Designation:'),   _val(rec.get('designation', '')),
             _lbl('Pay Period:'),    _val(f'{period_start} to {period_end}')],
            [Paragraph('', N),       Paragraph('', N),
             _lbl('Salary Date:'),   _val(salary_date)],
        ]
        info_tbl = Table(info_data, colWidths=[3.5*cm, 5.5*cm, 3.0*cm, 5.4*cm])
        info_tbl.setStyle(TableStyle([
            ('FONTSIZE',      (0,0), (-1,-1), 9),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING',   (0,0), (-1,-1), 6),
            ('RIGHTPADDING',  (0,0), (-1,-1), 6),
            ('BACKGROUND',    (0,0), (-1,-1), LIGHT_BG),
            ('GRID',          (0,0), (-1,-1), 0.4, GREY_LINE),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(info_tbl)
        story.append(Spacer(1, 6))

        att_tbl = Table([[
            Paragraph(f'<b>Total Days:</b> {total_days}',     N),
            Paragraph(f'<b>Working Days:</b> {working_days}', N),
            Paragraph(f'<b>Absent Days:</b> {absent_days}',   N),
        ]], colWidths=[5.8*cm, 5.8*cm, 5.8*cm])
        att_tbl.setStyle(TableStyle([
            ('FONTSIZE',      (0,0), (-1,-1), 9),
            ('TOPPADDING',    (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING',   (0,0), (-1,-1), 10),
            ('RIGHTPADDING',  (0,0), (-1,-1), 10),
            ('BACKGROUND',    (0,0), (-1,-1), ALT_ROW),
            ('GRID',          (0,0), (-1,-1), 0.4, GREY_LINE),
            ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ]))
        story.append(att_tbl)
        story.append(Spacer(1, 8))

        gross_tbl = Table([[
            Paragraph(
                f'<b>GROSS SALARY (Before Adjustments): {_currency(rec["gross_salary"])}</b>',
                ParagraphStyle('GB', fontSize=10, fontName='Helvetica-Bold',
                               textColor=WHITE, alignment=TA_CENTER)
            )
        ]], colWidths=[17.4*cm])
        gross_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), PRIMARY),
            ('TOPPADDING',    (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(gross_tbl)
        story.append(Spacer(1, 0))

        def _earn(label, val):
            return [Paragraph(label, N),
                    Paragraph(_currency(val), ParagraphStyle(
                        'EV', fontSize=9, fontName='Helvetica',
                        textColor=GREEN, alignment=TA_RIGHT))]

        def _ded(label, val):
            return [Paragraph(label, N),
                    Paragraph(_currency(val), ParagraphStyle(
                        'DV', fontSize=9, fontName='Helvetica',
                        textColor=RED, alignment=TA_RIGHT))]

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
            _ded('Provident Fund (PF)',    rec['pf']),
            _ded('Professional Tax (PT)', rec['pt']),
            _ded('Other Deductions',      rec['other_deduction']),
        ]
        blank = [Paragraph('', N), Paragraph('', N)]
        max_r = max(len(earn_rows), len(ded_rows))
        while len(earn_rows) < max_r: earn_rows.append(blank)
        while len(ded_rows)  < max_r: ded_rows.append(blank)

        earn_hdr = Paragraph('<b>EARNINGS (After Adjustment)</b>',
                             ParagraphStyle('EH', fontSize=9, fontName='Helvetica-Bold',
                                            textColor=WHITE))
        ded_hdr  = Paragraph('<b>DEDUCTIONS</b>',
                             ParagraphStyle('DH', fontSize=9, fontName='Helvetica-Bold',
                                            textColor=WHITE))

        ed_data = [[earn_hdr, '', '', ded_hdr, '']]
        for e, d in zip(earn_rows, ded_rows):
            ed_data.append([e[0], e[1], '', d[0], d[1]])

        total_ded = sum(v for v in [
            rec['pf'], rec['pt'], rec['other_deduction'], rec['absent_days_deduction']
        ] if v)

        last_r = len(ed_data)
        ed_data.append([
            Paragraph('<b>TOTAL EARNINGS:</b>',
                      ParagraphStyle('TE', fontSize=9, fontName='Helvetica-Bold',
                                     textColor=GREEN)),
            Paragraph(_currency(rec['gross_salary']),
                      ParagraphStyle('TEV', fontSize=9, fontName='Helvetica-Bold',
                                     textColor=GREEN, alignment=TA_RIGHT)),
            '',
            Paragraph('<b>TOTAL DEDUCTIONS:</b>',
                      ParagraphStyle('TD2', fontSize=9, fontName='Helvetica-Bold',
                                     textColor=RED)),
            Paragraph(_currency(total_ded),
                      ParagraphStyle('TDV', fontSize=9, fontName='Helvetica-Bold',
                                     textColor=RED, alignment=TA_RIGHT)),
        ])

        ed_tbl = Table(ed_data, colWidths=[5.0*cm, 3.0*cm, 0.4*cm, 5.8*cm, 3.2*cm])
        ed_tbl.setStyle(TableStyle([
            ('BACKGROUND',     (0,0),       (1,0),        PRIMARY),
            ('BACKGROUND',     (3,0),       (4,0),        PRIMARY),
            ('SPAN',           (0,0),       (1,0)),
            ('SPAN',           (3,0),       (4,0)),
            ('ALIGN',          (0,0),       (1,0),        'CENTER'),
            ('ALIGN',          (3,0),       (4,0),        'CENTER'),
            ('TOPPADDING',     (0,0),       (-1,0),       7),
            ('BOTTOMPADDING',  (0,0),       (-1,0),       7),
            ('FONTSIZE',       (0,1),       (-1,-1),      9),
            ('TOPPADDING',     (0,1),       (-1,-2),      5),
            ('BOTTOMPADDING',  (0,1),       (-1,-2),      5),
            ('LEFTPADDING',    (0,0),       (-1,-1),      6),
            ('RIGHTPADDING',   (0,0),       (-1,-1),      6),
            ('ROWBACKGROUNDS', (0,1),       (1,last_r-1), [WHITE, ALT_ROW]),
            ('ROWBACKGROUNDS', (3,1),       (4,last_r-1), [WHITE, ALT_ROW]),
            ('GRID',           (0,0),       (1,-1),       0.4, GREY_LINE),
            ('GRID',           (3,0),       (4,-1),       0.4, GREY_LINE),
            ('BACKGROUND',     (2,0),       (2,-1),       WHITE),
            ('LINEAFTER',      (2,0),       (2,-1),       0, WHITE),
            ('LINEBEFORE',     (2,0),       (2,-1),       0, WHITE),
            ('BACKGROUND',     (0,last_r),  (1,last_r),   LIGHT_BG),
            ('BACKGROUND',     (3,last_r),  (4,last_r),   LIGHT_BG),
            ('TOPPADDING',     (0,last_r),  (-1,last_r),  7),
            ('BOTTOMPADDING',  (0,last_r),  (-1,last_r),  7),
            ('LINEABOVE',      (0,last_r),  (1,last_r),   1.2, PRIMARY),
            ('LINEABOVE',      (3,last_r),  (4,last_r),   1.2, PRIMARY),
            ('ALIGN',          (1,last_r),  (1,last_r),   'RIGHT'),
            ('ALIGN',          (4,last_r),  (4,last_r),   'RIGHT'),
        ]))
        story.append(ed_tbl)
        story.append(Spacer(1, 10))

        net_tbl = Table([[
            Paragraph(
                f'<b>NET SALARY: {_currency(rec["net_salary"])}</b>',
                ParagraphStyle('NB', fontSize=13, fontName='Helvetica-Bold',
                               textColor=WHITE, alignment=TA_CENTER)
            )
        ]], colWidths=[17.4*cm])
        net_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), GREEN),
            ('TOPPADDING',    (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(net_tbl)
        story.append(Spacer(1, 18))

        note_style = ParagraphStyle('Note', fontSize=8, fontName='Helvetica-Oblique',
                                    textColor=colors.grey, spaceAfter=3)
        for note in [
            '• This is a system-generated salary slip and does not require a signature.',
            '• For any queries regarding this salary slip, please contact the HR department.',
            f'• Generated on: {datetime.now().strftime("%Y-%m-%d")}',
        ]:
            story.append(Paragraph(note, note_style))

        story.append(Spacer(1, 10))
        story.append(HRFlowable(width='100%', thickness=0.5, color=GREY_LINE))
        story.append(Paragraph(
            'Confidential \u2014 For Internal Use Only.',
            ParagraphStyle('footer2', fontSize=8, fontName='Helvetica-Oblique',
                           textColor=colors.grey, alignment=TA_CENTER, spaceBefore=4)
        ))

        doc.build(story)
        buf.seek(0)
        safe_name = (rec['Name'] or 'Employee').replace(' ', '_')
        return send_file(buf, mimetype='application/pdf', as_attachment=True,
                         download_name=f"SalarySlip_{safe_name}_{salary_month}.pdf")

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()