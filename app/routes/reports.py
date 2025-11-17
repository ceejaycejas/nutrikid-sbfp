from flask import Blueprint, render_template, send_file, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.models.section import Section
from app.models.student import Student
from app.models.school import School
from app.models.notification import Notification
from app.models.user import User
from app.models.user_activity import UserActivity
from app.services.notification_service import NotificationService
from app.services.email_service import EmailService
from app import db
import io
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import func, extract
import xlsxwriter
import os
from flask import current_app
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart

def log_activity(user_id, activity_type, description, ip_address=None):
    activity = UserActivity(user_id=user_id, activity_type=activity_type, description=description, ip_address=ip_address)
    db.session.add(activity)
    db.session.commit()

bp = Blueprint('reports', __name__, url_prefix='/reports')

@bp.route('/')
@login_required
def index():
    log_activity(current_user.id, 'view_reports', 'Accessed reports page', request.remote_addr)
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    # Get all students for the admin's school
    students = Student.query.filter_by(school_id=current_user.school_id).all()
    return render_template('reports/index.html', students=students)

@bp.route('/export')
@login_required
def export():
    try:
        log_activity(current_user.id, 'export_report', 'Exported student data report', request.remote_addr)
        if current_user.role != 'admin':
            flash('Unauthorized access', 'danger')
            return redirect(url_for('school.dashboard'))
        
        # Get school and students
        school = School.query.get(current_user.school_id)
        students = Student.query.filter_by(school_id=current_user.school_id).all()
        
        # Create Excel file in memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'font_color': '#FFFFFF',
            'bg_color': '#4F81BD',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        subheader_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'font_color': '#FFFFFF',
            'bg_color': '#70AD47',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        data_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter'
        })
        
        center_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        number_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'num_format': '0.0'
        })
        
        # Create main worksheet
        worksheet = workbook.add_worksheet('Student Data')
        
        # Set column widths
        worksheet.set_column('A:A', 5)   # Index
        worksheet.set_column('B:B', 25)  # Name
        worksheet.set_column('C:C', 15)  # Section
        worksheet.set_column('D:D', 10)  # Gender
        worksheet.set_column('E:E', 15)  # Birth Date
        worksheet.set_column('F:F', 8)   # Age
        worksheet.set_column('G:G', 12)  # Height
        worksheet.set_column('H:H', 12)  # Weight
        worksheet.set_column('I:I', 8)   # BMI
        worksheet.set_column('J:J', 25)  # Preferences/Allergies
        
        # Add school information with proper arrangement (matching PDF sample)
        row = 0
        
        # Department of Education header
        dept_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center'})
        worksheet.merge_range(row, 0, row, 9, 'Department of Education', dept_format)
        row += 1
        
        # Region header
        region_format = workbook.add_format({'bold': True, 'font_size': 12, 'align': 'center'})
        worksheet.merge_range(row, 0, row, 9, 'Region XI', region_format)
        row += 1
        
        # Title
        title_format = workbook.add_format({'bold': True, 'font_size': 12, 'align': 'center'})
        worksheet.merge_range(row, 0, row, 9, 'List Beneficiaries for School-Based Feeding Program (SBFP)', title_format)
        row += 1
        
        # School Year
        sy_format = workbook.add_format({'bold': True, 'font_size': 12, 'align': 'center'})
        worksheet.merge_range(row, 0, row, 9, '(SY 2025-2026)', sy_format)
        row += 2
        
        # Division/Province
        worksheet.write(row, 0, 'Division/Province: _________________', data_format)
        worksheet.write(row, 5, 'Name of Principal: _________________', data_format)
        row += 1
        
        # City/Municipality/Barangay
        worksheet.write(row, 0, 'City/Municipality/Barangay: _________', data_format)
        worksheet.write(row, 5, 'Name of Feeding Focal Person: _______', data_format)
        row += 1
        
        # School Information
        worksheet.write(row, 0, f'Name of School: {school.name if school else "__________________"}', data_format)
        worksheet.write(row, 5, 'School ID Number: ________________', data_format)
        row += 2
        
        # Add student data table header (matching PDF format)
        headers = ['Name', 'Level/Section', 'Gender', 'Birthdate', 'Age', 'Height (cm)', 'Weight (kg)', 'BMI', 'Preferences']
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)
        row += 1
        
        # Add student data (matching PDF format)
        for s in students:
            worksheet.write(row, 0, s.name if s.name else '', data_format)  # Name
            # Combine level and section
            level_section = ''
            if s.section:
                level_section = f"{s.section.grade_level.name if s.section.grade_level else ''}/{s.section.name if s.section else ''}"
            worksheet.write(row, 1, level_section, data_format)  # Level/Section
            worksheet.write(row, 2, s.gender if s.gender else '', center_format)  # Gender
            worksheet.write(row, 3, s.birth_date.strftime('%Y-%m-%d') if s.birth_date else '', center_format)  # Birthdate
            worksheet.write(row, 4, s.age if hasattr(s, 'age') and s.age is not None else '', center_format)  # Age
            worksheet.write(row, 5, s.height if s.height is not None else '', center_format)  # Height
            worksheet.write(row, 6, s.weight if s.weight is not None else '', center_format)  # Weight
            worksheet.write(row, 7, s.bmi if hasattr(s, 'bmi') and s.bmi is not None else '', number_format)  # BMI
            worksheet.write(row, 8, s.preferences if hasattr(s, 'preferences') and s.preferences else '', data_format)  # Preferences
            row += 1
        
        # Add charts and distribution information at the end (matching PDF format)
        row += 2
        chart_title_format = workbook.add_format({'bold': True, 'font_size': 12, 'align': 'center'})
        worksheet.merge_range(row, 0, row, 4, 'BMI Classification Distribution', chart_title_format)
        row += 15  # Space for chart
        
        row += 2
        worksheet.merge_range(row, 0, row, 4, 'Gender Distribution', chart_title_format)
        row += 15  # Space for chart
        
        # Footer
        row += 2
        footer_format = workbook.add_format({'italic': True, 'font_size': 10, 'align': 'center'})
        worksheet.merge_range(row, 0, row, 9, 'Generated by the Nutrition Monitoring System', footer_format)
        
        # Close workbook
        workbook.close()
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            download_name=f'{(school.name if school else "School").replace(" ", "_")}_nutritional_report_{datetime.now().strftime("%Y%m%d")}.xlsx',
            as_attachment=True
        )
    
    except Exception as e:
        # Log the error
        print(f"Export error: {str(e)}")
        flash(f'Error exporting data: {str(e)}', 'danger')
        return redirect(url_for('reports.index'))

@bp.route('/export_pdf')
@login_required
def export_pdf():
    try:
        log_activity(current_user.id, 'export_pdf_report', 'Exported student data report as PDF', request.remote_addr)
        if current_user.role != 'admin':
            flash('Unauthorized access', 'danger')
            return redirect(url_for('school.dashboard'))

        # Fetch data
        school = School.query.get(current_user.school_id)
        students = Student.query.filter_by(school_id=current_user.school_id).all()

        # Prepare PDF buffer
        output = io.BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
            title="Student Nutritional Records"
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="CenterSmall", alignment=TA_CENTER, fontSize=10))
        styles.add(ParagraphStyle(name="Center", alignment=TA_CENTER, fontSize=12, leading=14))
        styles.add(ParagraphStyle(name="Small", alignment=TA_LEFT, fontSize=9))

        flow = []

        # Helper to resolve static paths
        def static_path(relative_path: str) -> str:
            base = os.path.join(current_app.root_path, 'static')
            return os.path.join(base, relative_path.replace('\\', '/'))

        # Resolve school logo (left)
        school_logo_path = None
        if school and school.logo:
            candidate = static_path(school.logo) if not os.path.isabs(school.logo) else school.logo
            if os.path.exists(candidate):
                school_logo_path = candidate
        # Fallbacks
        if not school_logo_path:
            # Use user's profile image if present, else default app logo
            school_logo_path = static_path('img/LOGO1.png')

        # Right-side logo (DepEd seal preferred)
        # Try multiple common filenames
        deped_candidates = [
            static_path('img/depedlogo.png'),
            static_path('img/deped.png'),
        ]
        right_logo_path = None
        for c in deped_candidates:
            if os.path.exists(c):
                right_logo_path = c
                break
        if not right_logo_path:
            right_logo_path = static_path('img/LOGO.png') if os.path.exists(static_path('img/LOGO.png')) else static_path('img/LOGO1.png')

        # Header with logos and titles
        header_table_data = [
            [
                Image(school_logo_path, width=2.2 * cm, height=2.2 * cm),
                Paragraph("<b>Department of Education</b><br/>Region XI<br/><b>List Beneficiaries for School-Based Feeding Program (SBFP)</b><br/>(SY2025-2026)", styles["Center"]),
                Image(right_logo_path, width=2.2 * cm, height=2.2 * cm),
            ]
        ]
        header_tbl = Table(header_table_data, colWidths=[3 * cm, None, 3 * cm])
        header_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ]))
        flow.append(header_tbl)
        flow.append(Spacer(1, 0.6 * cm))

        # School/Principal information lines
        def line(label, value='__________________'):
            return Paragraph(f"{label}: {value}", styles["Small"])

        info_table = Table([
            [line("Division/Province"), line("Name of Principal")],
            [line("City/ Municipality/Barangay"), line("Name of Feeding Focal Person")],
            [line("Name of School", (school.name if school else '__________________')), line("School ID Number")],
        ], colWidths=[9.0 * cm, 6.5 * cm])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        flow.append(info_table)
        # Add more vertical space before the data table to avoid any visual overlap
        flow.append(Spacer(1, 1.0 * cm))

        # Student table
        # PDF export: exclude Preferences column for a concise report
        headers = ["Name", "Level/Section", "Gender", "Birthdate", "Age", "Height(cm)", "Weight(kg)", "BMI"]
        table_data = [headers]
        # style for wrapped cells
        wrap_style = ParagraphStyle('wrap', parent=styles['Small'], fontSize=9, leading=11)
        for s in students:
            level_section = ''
            if s.section:
                level_section = f"{s.section.grade_level.name if getattr(s.section, 'grade_level', None) else ''}/{s.section.name}"
            # Fix: Don't create Paragraph objects here, just use strings
            table_data.append([
                s.name or "",
                level_section,
                s.gender or "",
                s.birth_date.strftime('%Y-%m-%d') if s.birth_date else "",
                str(getattr(s, 'age', '') or ""),
                str(s.height if s.height is not None else ""),
                str(s.weight if s.weight is not None else ""),
                f"{s.bmi:.1f}" if getattr(s, 'bmi', None) is not None else "",
            ])

        # wider Name and Preferences, fixed compact technical columns
        tbl = Table(
            table_data,
            repeatRows=1,
            # Adjusted widths after removing Preferences column; give Name more room
            colWidths=[8.0*cm, 3.8*cm, 1.8*cm, 2.8*cm, 1.4*cm, 2.2*cm, 2.2*cm, 1.9*cm]
        )
        table_style = TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (2, 1), (7, -1), 'CENTER'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#c5c9d3')),  # stronger header separator
            ('GRID', (0, 1), (-1, -1), 0.5, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9eefb')),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ])
        # Zebra striping for readability
        for i in range(1, len(table_data)):
            if i % 2 == 1:
                table_style.add('BACKGROUND', (0, i), (-1, i), colors.whitesmoke)
        tbl.setStyle(table_style)
        flow.append(tbl)
        flow.append(Spacer(1, 0.8 * cm))

        # Charts section with clear titles and legends
        # Compute BMI distribution
        bmi_counts = {'Underweight': 0, 'Normal': 0, 'Overweight': 0, 'Obese': 0}
        for s in students:
            b = getattr(s, 'bmi', None)
            if b is None:
                continue
            if b < 18.5:
                bmi_counts['Underweight'] += 1
            elif b < 25:
                bmi_counts['Normal'] += 1
            elif b < 30:
                bmi_counts['Overweight'] += 1
            else:
                bmi_counts['Obese'] += 1

        total_bmi = sum(bmi_counts.values())
        # Restore balanced chart size for a professional look
        drawing1 = Drawing(220, 140)
        pie = Pie()
        pie.x = 5
        pie.y = 10
        pie.width = 110
        pie.height = 110
        pie.data = list(bmi_counts.values()) if total_bmi > 0 else [1]
        pie.labels = []
        pie.slices.strokeWidth = 0.5
        pie.slices[0].fillColor = colors.HexColor('#ffc107')  # Underweight
        pie.slices[1].fillColor = colors.HexColor('#28a745')  # Normal
        pie.slices[2].fillColor = colors.HexColor('#fd7e14')  # Overweight
        pie.slices[3].fillColor = colors.HexColor('#dc3545')  # Obese
        drawing1.add(pie)
        # Legend as paragraphs with counts and percentages (placed beside pie)
        legend_items = []
        legend_pairs = [('Underweight', pie.slices[0].fillColor),
                        ('Normal', pie.slices[1].fillColor),
                        ('Overweight', pie.slices[2].fillColor),
                        ('Obese', pie.slices[3].fillColor)]
        if total_bmi == 0:
            legend_items.append(Paragraph('No BMI data available', styles['Small']))
        else:
            for label, color in legend_pairs:
                count = bmi_counts[label]
                pct = (count / total_bmi * 100) if total_bmi else 0
                legend_items.append(Paragraph(f'<font color="{color.hexval()}">■</font> {label}: {count} ({pct:.1f}%)', styles['Small']))
        legend_tbl = Table([[li] for li in legend_items], colWidths=[150])
        legend_tbl.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        bmi_caption = Paragraph("<b>BMI Classification Distribution</b>", styles["CenterSmall"])
        bmi_block = Table([[drawing1, legend_tbl],
                           [Spacer(1, 2), Spacer(1, 2)],
                           [bmi_caption, Spacer(1, 0)]],
                          colWidths=[130, 170])
        bmi_block.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))

        # Gender distribution chart with counts shown on bars
        flow.append(Spacer(1, 0.6 * cm))

        male = sum(1 for s in students if (s.gender or '').lower().startswith('m'))
        female = sum(1 for s in students if (s.gender or '').lower().startswith('f'))
        drawing2 = Drawing(300, 140)
        bar = VerticalBarChart()
        bar.x = 40
        bar.y = 25
        bar.height = 90
        bar.width = 220
        bar.data = [[male, female]]
        bar.categoryAxis.categoryNames = ['Male', 'Female']
        bar.valueAxis.valueMin = 0
        bar.barWidth = 28
        bar.strokeColor = colors.black
        bar.bars[0].fillColor = colors.HexColor('#ff4757')
        drawing2.add(bar)
        # Add numeric labels above bars
        vals = [male, female]
        for i, v in enumerate(vals):
            x = bar.x + (i + 0.5) * (bar.width / len(vals))
            drawing2.add(String(x - 4, bar.y + bar.height + 5, str(v), fontSize=9))
        gender_caption = Paragraph("<b>Gender Distribution</b>", styles["CenterSmall"])
        gender_block = Table([[drawing2],
                              [Spacer(1, 2)],
                              [gender_caption]], colWidths=[300])
        gender_block.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))

        charts_table = Table([[bmi_block, gender_block]], colWidths=[8 * cm, 8 * cm])
        charts_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        flow.append(charts_table)
        flow.append(Spacer(1, 0.6 * cm))

        # Footer
        flow.append(Spacer(1, 0.6 * cm))
        flow.append(Paragraph("Generated by the Nutrition Monitoring System", styles["CenterSmall"]))

        # Build PDF
        doc.build(flow)
        output.seek(0)

        safe_school = (school.name if school else 'School').replace(' ', '_')
        filename = f'{safe_school}_nutritional_report_{datetime.now().strftime("%Y%m%d")}.pdf'
        return send_file(output, mimetype='application/pdf', download_name=filename, as_attachment=True)

    except Exception as e:
        # Log the error with full traceback
        import traceback
        error_msg = f"PDF Export error: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        print(error_msg)
        flash(f'Error exporting PDF data: {str(e)}', 'danger')
        return redirect(url_for('reports.index'))

@bp.route('/send-to-super-admin', methods=['POST'])
@login_required
def send_to_super_admin():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('reports.index'))
    
    try:
        # Find all super admins
        super_admins = User.query.filter_by(role='super_admin').all()
        admin_school = School.query.get(current_user.school_id)
        
        # Get student count for the report
        student_count = Student.query.filter_by(school_id=current_user.school_id).count()
        
        # Create notification for each super admin using notification service
        title = "New Student Nutritional Report Submitted"
        message = f"Admin {current_user.name} from {admin_school.name if admin_school else 'Unknown School'} has submitted a nutritional report for {student_count} students."
        
        for sa in super_admins:
            NotificationService.create_notification(
                recipient_id=sa.id,
                title=title,
                message=message,
                notification_type='report_generated',
                priority='medium',
                related_entity_type='school',
                related_entity_id=current_user.school_id,
                action_url='/super_admin/reports',
                action_text='View Reports'
            )
            
            # Send email notification to super admin
            try:
                EmailService.send_report_notification_to_super_admin(
                    super_admin_email=sa.email,
                    super_admin_name=sa.name,
                    admin_name=current_user.name,
                    school_name=admin_school.name if admin_school else 'Unknown School',
                    student_count=student_count
                )
            except Exception as e:
                current_app.logger.error(f"Failed to send email notification to super admin {sa.email}: {str(e)}")
        
        db.session.commit()
        log_activity(current_user.id, 'send_report', f'Sent nutritional report to super admins for {student_count} students', request.remote_addr)
        flash('Report sent successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error sending report. Please try again.', 'danger')
        log_activity(current_user.id, 'send_report_error', f'Failed to send report: {str(e)}', request.remote_addr)
    
    return redirect(url_for('reports.index'))



@bp.route('/api/nutritional-status')
@login_required
def api_nutritional_status():
    """API endpoint for Consolidated Student Nutritional Status Report (Doughnut Chart)"""
    if current_user.role not in ['admin', 'super_admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get students based on user role
        if current_user.role == 'super_admin':
            students = Student.query.all()
        else:
            students = Student.query.filter_by(school_id=current_user.school_id).all()
        
        # Categorize students by BMI status
        categories = {
            'Underweight': 0,
            'Normal Weight': 0,
            'Overweight': 0,
            'Obese': 0,
            'No Data': 0
        }
        
        for student in students:
            if student.bmi is None:
                categories['No Data'] += 1
            elif student.bmi < 18.5:
                categories['Underweight'] += 1
            elif student.bmi < 25:
                categories['Normal Weight'] += 1
            elif student.bmi < 30:
                categories['Overweight'] += 1
            else:
                categories['Obese'] += 1
        
        total_students = len(students)
        data = []
        colors = ['#ffc107', '#28a745', '#fd7e14', '#dc3545', '#6c757d']  # Yellow, Green, Orange, Red, Gray
        
        for i, (category, count) in enumerate(categories.items()):
            percentage = (count / total_students * 100) if total_students > 0 else 0
            data.append({
                'label': category,
                'value': count,
                'percentage': round(percentage, 1),
                'color': colors[i]
            })
        
        return jsonify({
            'success': True,
            'data': data,
            'total_students': total_students
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/school-performance')
@login_required
def api_school_performance():
    """API endpoint for School Performance Overview (Bar Chart)"""
    if current_user.role not in ['admin', 'super_admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get schools based on user role
        if current_user.role == 'super_admin':
            schools = School.query.all()
        else:
            schools = [School.query.get(current_user.school_id)] if current_user.school_id else []
        
        data = []
        colors = ['#007bff', '#28a745', '#ffc107', '#fd7e14', '#dc3545', '#6f42c1', '#20c997', '#e83e8c']
        
        for i, school in enumerate(schools):
            # Fix: Check if school is not None before accessing its attributes
            if school is None:
                continue
            students = Student.query.filter_by(school_id=school.id).all()
            total_students = len(students)
            
            # Calculate metrics
            beneficiaries = sum(1 for s in students if s.is_beneficiary)
            at_risk = sum(1 for s in students if s.is_at_risk)
            completion_rate = (beneficiaries / total_students * 100) if total_students > 0 else 0
            
            data.append({
                'school_name': school.name,
                'total_students': total_students,
                'beneficiaries_served': beneficiaries,
                'at_risk_students': at_risk,
                'completion_rate': round(completion_rate, 1),
                'color': colors[i % len(colors)]
            })
        
        return jsonify({
            'success': True,
            'data': data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/progress-report')
@login_required
def api_progress_report():
    """API endpoint for Comparative Progress Report (Line Chart)"""
    if current_user.role not in ['admin', 'super_admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get last 6 months data
        months_data = []
        current_date = datetime.now()
        
        for i in range(6):
            month_date = current_date - timedelta(days=30*i)
            month_name = month_date.strftime('%B %Y')
            
            # Get students created before this month
            if current_user.role == 'super_admin':
                students = Student.query.filter(Student.created_at <= month_date).all()
            else:
                students = Student.query.filter(
                    Student.created_at <= month_date,
                    Student.school_id == current_user.school_id
                ).all()
            
            # Calculate metrics
            total_students = len(students)
            beneficiaries = sum(1 for s in students if s.is_beneficiary)
            healthy_students = sum(1 for s in students if s.bmi and 18.5 <= s.bmi < 25)
            
            coverage_rate = (beneficiaries / total_students * 100) if total_students > 0 else 0
            health_rate = (healthy_students / total_students * 100) if total_students > 0 else 0
            
            months_data.append({
                'month': month_name,
                'total_students': total_students,
                'coverage_rate': round(coverage_rate, 1),
                'health_rate': round(health_rate, 1)
            })
        
        months_data.reverse()  # Show oldest to newest
        
        return jsonify({
            'success': True,
            'data': months_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/compliance-audit')
@login_required
def api_compliance_audit():
    """API endpoint for Compliance & Audit Report (Stacked Bar Chart)"""
    if current_user.role not in ['admin', 'super_admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get schools based on user role
        if current_user.role == 'super_admin':
            schools = School.query.all()
        else:
            schools = [School.query.get(current_user.school_id)] if current_user.school_id else []
        
        data = []
        colors = ['#007bff', '#28a745', '#ffc107', '#fd7e14', '#dc3545', '#6f42c1', '#20c997', '#e83e8c']
        
        for i, school in enumerate(schools):
            # Fix: Check if school is not None before accessing its attributes
            if school is None:
                continue
            students = Student.query.filter_by(school_id=school.id).all()
            total_students = len(students)
            
            if total_students == 0:
                continue
            
            # Calculate compliance metrics
            complete_records = sum(1 for s in students if s.bmi and s.height and s.weight)
            partial_records = sum(1 for s in students if (s.height or s.weight) and not (s.height and s.weight))
            incomplete_records = total_students - complete_records - partial_records
            
            # Calculate percentages
            complete_pct = (complete_records / total_students * 100) if total_students > 0 else 0
            partial_pct = (partial_records / total_students * 100) if total_students > 0 else 0
            incomplete_pct = (incomplete_records / total_students * 100) if total_students > 0 else 0
            
            data.append({
                'school_name': school.name,
                'total_students': total_students,
                'complete_records': complete_records,
                'partial_records': partial_records,
                'incomplete_records': incomplete_records,
                'complete_pct': round(complete_pct, 1),
                'partial_pct': round(partial_pct, 1),
                'incomplete_pct': round(incomplete_pct, 1),
                'color': colors[i % len(colors)]
            })
        
        return jsonify({
            'success': True,
            'data': data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500