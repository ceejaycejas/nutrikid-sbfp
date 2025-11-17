from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.school import School
from app.models.section import Section
from app.models.student import Student
from datetime import datetime
from app.routes.school import log_activity
from app.services.notification_service import NotificationService
from app.services.email_service import EmailService
import io
import xlsxwriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

bp = Blueprint('super_admin', __name__, url_prefix='/super-admin')

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    log_activity(current_user.id, 'dashboard_access', 'Accessed super admin dashboard', request.remote_addr)
    
    # Get school filter from request
    school_id = request.args.get('school_id', type=int)
    selected_school = None
    
    # Get all schools for dropdown
    all_schools = School.query.order_by(School.name).all()
    
    # Build base query filters based on school selection
    student_filter = Student.query
    admin_filter = User.query.filter_by(role='admin')
    section_filter = Section.query
    
    if school_id:
        selected_school = School.query.get(school_id)
        if selected_school:
            student_filter = student_filter.filter(Student.school_id == school_id)
            admin_filter = admin_filter.filter(User.school_id == school_id)
            section_filter = section_filter.filter(Section.school_id == school_id)
    
    # Get filtered statistics
    total_schools = School.query.count() if not school_id else 1
    total_admins = admin_filter.count()
    total_students = student_filter.count()
    total_super_admins = User.query.filter_by(role='super_admin').count()
    total_sections = section_filter.count()
    
    # Get recent activities (last 10) - filtered by school if selected
    recent_activities_query = db.session.query(
        User.name.label('user_name'),
        User.role.label('user_role'),
        School.name.label('school_name'),
        Student.name.label('activity_description'),
        Student.created_at.label('activity_time')
    ).select_from(Student)\
     .join(User, Student.registered_by == User.id)\
     .outerjoin(School, Student.school_id == School.id)
    
    if school_id:
        recent_activities_query = recent_activities_query.filter(Student.school_id == school_id)
    
    recent_activities = recent_activities_query.order_by(Student.created_at.desc()).limit(10).all()
    
    # Enhanced BMI distribution for filtered students with BMI data
    # Use consistent keys: 'severely_wasted', 'wasted', 'normal', 'overweight', 'obese'
    bmi_distribution = {
        'normal': 0,
        'underweight': 0,  # Keep for backward compatibility
        'overweight': 0,
        'obese': 0,
        'severely_underweight': 0,  # Keep for backward compatibility
        'severely_wasted': 0,  # Add for template compatibility
        'wasted': 0  # Add for template compatibility
    }
    
    # Get filtered students with BMI data
    students_with_bmi_query = student_filter.filter(Student.bmi.isnot(None))
    students_with_bmi = students_with_bmi_query.all()
    
    for student in students_with_bmi:
        if student.bmi < 16:
            bmi_distribution['severely_underweight'] += 1
            bmi_distribution['severely_wasted'] += 1  # Also count as severely_wasted
        elif student.bmi < 18.5:
            bmi_distribution['underweight'] += 1
            bmi_distribution['wasted'] += 1  # Also count as wasted
        elif student.bmi < 25:
            bmi_distribution['normal'] += 1
        elif student.bmi < 30:
            bmi_distribution['overweight'] += 1
        else:
            bmi_distribution['obese'] += 1
    
    # Schools with most students (only if no school filter)
    if not school_id:
        school_stats = db.session.query(
            School.name,
            db.func.count(Student.id).label('student_count')
        ).outerjoin(Student, School.id == Student.school_id)\
         .group_by(School.id, School.name)\
         .order_by(db.func.count(Student.id).desc())\
         .limit(5).all()
    else:
        # If filtered, show only the selected school
        school_stats = db.session.query(
            School.name,
            db.func.count(Student.id).label('student_count')
        ).outerjoin(Student, School.id == Student.school_id)\
         .filter(School.id == school_id)\
         .group_by(School.id, School.name).all()
    
    # Monthly student registrations for the past 12 months - filtered
    from datetime import datetime, timedelta
    from sqlalchemy import extract
    
    monthly_registrations_query = db.session.query(
        extract('month', Student.created_at).label('month'),
        extract('year', Student.created_at).label('year'),
        db.func.count(Student.id).label('count')
    ).filter(Student.created_at >= datetime.utcnow() - timedelta(days=365))
    
    if school_id:
        monthly_registrations_query = monthly_registrations_query.filter(Student.school_id == school_id)
    
    monthly_registrations = monthly_registrations_query.group_by(extract('year', Student.created_at), extract('month', Student.created_at))\
     .order_by(extract('year', Student.created_at), extract('month', Student.created_at)).all()
    
    # Gender distribution - filtered
    gender_distribution_query = db.session.query(
        Student.gender,
        db.func.count(Student.id).label('count')
    ).filter(Student.gender.isnot(None))
    
    if school_id:
        gender_distribution_query = gender_distribution_query.filter(Student.school_id == school_id)
    
    gender_distribution = gender_distribution_query.group_by(Student.gender).all()
    
    # Beneficiary vs Non-beneficiary distribution - filtered
    beneficiary_query = student_filter.filter_by(is_beneficiary=True)
    non_beneficiary_query = student_filter.filter_by(is_beneficiary=False)
    
    beneficiary_distribution = {
        'beneficiaries': beneficiary_query.count(),
        'non_beneficiaries': non_beneficiary_query.count()
    }
    
    # Students by age groups - filtered
    age_groups = {
        '5-8': 0,
        '9-12': 0,
        '13-16': 0,
        '17+': 0
    }
    
    filtered_students = student_filter.all()
    for student in filtered_students:
        if student.age:
            if 5 <= student.age <= 8:
                age_groups['5-8'] += 1
            elif 9 <= student.age <= 12:
                age_groups['9-12'] += 1
            elif 13 <= student.age <= 16:
                age_groups['13-16'] += 1
            elif student.age >= 17:
                age_groups['17+'] += 1
    
    # Recent system activity (last 7 days)
    from app.models.user_activity import UserActivity
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_system_activity = UserActivity.query.filter(
        UserActivity.created_at >= seven_days_ago
    ).order_by(UserActivity.created_at.desc()).limit(15).all()
    
    # Students at risk (BMI-based) - filtered
    at_risk_query = student_filter.filter(
        Student.bmi.isnot(None),
        (Student.bmi < 18.5) | (Student.bmi >= 25)
    )
    at_risk_students = at_risk_query.count()
    
    # System health metrics
    system_metrics = {
        'total_users': total_super_admins + total_admins + total_students,
        'active_schools': total_schools,
        'students_with_bmi': len(students_with_bmi),
        'at_risk_students': at_risk_students,
        'beneficiary_coverage': (beneficiary_distribution['beneficiaries'] / max(total_students, 1)) * 100 if total_students > 0 else 0
    }
    
    return render_template('super_admin/dashboard.html',
                         total_schools=total_schools,
                         total_admins=total_admins,
                         total_students=total_students,
                         total_super_admins=total_super_admins,
                         total_sections=total_sections,
                         recent_activities=recent_activities,
                         bmi_distribution=bmi_distribution,
                         school_stats=school_stats,
                         monthly_registrations=monthly_registrations,
                         gender_distribution=gender_distribution,
                         beneficiary_distribution=beneficiary_distribution,
                         age_groups=age_groups,
                         recent_system_activity=recent_system_activity,
                         system_metrics=system_metrics,
                         all_schools=all_schools,
                         selected_school=selected_school,
                         selected_school_id=school_id)

@bp.route('/users')
@login_required
def super_admins():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    users = User.query.filter(User.role == 'super_admin').all()
    return render_template('super_admin/users.html', users=users)

@bp.route('/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('super_admin.create_user'))
        
        user = User(name=name, email=email, role=role)
        user.set_password(password)
        
        # Set school if role is admin
        if role == 'admin':
            school_id = request.form.get('school_id')
            if school_id:
                user.school_id = int(school_id)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            # Send notification to the new user
            NotificationService.notify_account_created(
                user_id=user.id,
                password=password,
                created_by_name=current_user.name
            )
            
            flash('User created successfully!', 'success')
            return redirect(url_for('super_admin.super_admins'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'danger')
    
    schools = School.query.all()
    return render_template('super_admin/create_user.html', schools=schools)

@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.name = request.form.get('name')
        user.email = request.form.get('email')
        user.role = request.form.get('role')
        
        # Update school if role is admin
        if user.role == 'admin':
            school_id = request.form.get('school_id')
            if school_id:
                user.school_id = int(school_id)
        else:
            user.school_id = None
        
        # Update password if provided
        new_password = request.form.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        try:
            db.session.commit()
            
            # Prepare changes summary
            changes = []
            if user.name != request.form.get('name'):
                changes.append(f"Name updated")
            if user.email != request.form.get('email'):
                changes.append(f"Email updated")
            if user.role != request.form.get('role'):
                changes.append(f"Role changed to {user.role}")
            if new_password:
                changes.append("Password changed")
                # Send separate notification for password change
                NotificationService.notify_password_changed(
                    user_id=user.id,
                    changed_by_name=current_user.name
                )
            
            # Send general update notification
            if changes:
                NotificationService.notify_account_updated(
                    user_id=user.id,
                    updated_by_name=current_user.name,
                    changes="\n".join(changes)
                )
            
            flash('User updated successfully!', 'success')
            return redirect(url_for('super_admin.super_admins'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')
    
    schools = School.query.all()
    return render_template('super_admin/edit_user.html', user=user, schools=schools)

@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    try:
        # First, delete all user activities associated with this user
        from app.models.user_activity import UserActivity
        UserActivity.query.filter_by(user_id=user_id).delete()
        
        # Delete associated student profile if exists
        if user.student_profile:
            db.session.delete(user.student_profile)
        
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')
    
    return redirect(url_for('super_admin.super_admins'))

# --- ADMIN MANAGEMENT ---
@bp.route('/admins')
@login_required
def admins():
    log_activity(current_user.id, 'view_admins', 'Accessed admins management page', request.remote_addr)
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    search_query = request.args.get('search_query', '').strip()
    query = User.query.filter(User.role == 'admin')
    if search_query:
        # Use LIKE for MySQL (case-insensitive by default with utf8mb4_ci collation)
        search_pattern = f'%{search_query}%'
        query = query.filter(
            (User.name.like(search_pattern)) | 
            (User.email.like(search_pattern))
        )
    admins = query.all()
    return render_template('super_admin/admins.html', admins=admins, search_query=search_query)

@bp.route('/admins/create', methods=['GET', 'POST'])
@login_required
def create_admin():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        school_id = request.form.get('school_id')
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('super_admin.create_admin'))
        admin = User(name=name, email=email, role='admin', school_id=school_id)
        admin.set_password(password)
        try:
            db.session.add(admin)
            db.session.commit()
            school = School.query.get(school_id) if school_id else None
            
            # Send notifications
            NotificationService.notify_account_created(
                user_id=admin.id,
                password=password,
                created_by_name=current_user.name
            )
            
            if school:
                NotificationService.notify_admin_assignment(
                    user_id=admin.id,
                    school_name=school.name,
                    assigned_by_name=current_user.name
                )
            
            # Send welcome email to admin
            try:
                EmailService.send_welcome_email_admin(
                    admin_email=admin.email,
                    admin_name=admin.name,
                    password=password,
                    school_name=school.name if school else None,
                    created_by_name=current_user.name
                )
            except Exception as e:
                current_app.logger.error(f"Failed to send welcome email to admin {admin.email}: {str(e)}")
            
            log_activity(current_user.id, 'create_admin', f'Created admin {name} ({email}) for {school.name if school else "no school"}', request.remote_addr)
            flash('Admin created successfully!', 'success')
            return redirect(url_for('super_admin.admins'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating admin: {str(e)}', 'danger')
    schools = School.query.all()
    return render_template('super_admin/create_admin.html', schools=schools)

@bp.route('/admins/<int:admin_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_admin(admin_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    admin = User.query.filter_by(id=admin_id, role='admin').first_or_404()
    if request.method == 'POST':
        old_school_id = admin.school_id
        new_school_id = request.form.get('school_id')
        new_school_id = int(new_school_id) if new_school_id else None
        
        admin.name = request.form.get('name')
        admin.email = request.form.get('email')
        admin.school_id = new_school_id
        new_password = request.form.get('new_password')
        if new_password:
            admin.set_password(new_password)
        try:
            db.session.commit()
            
            # Notify if school assignment changed
            if old_school_id != new_school_id:
                from app.services.notification_service import NotificationService
                
                # Notify old school admins (if admin was moved from one school to another)
                if old_school_id:
                    old_school = School.query.get(old_school_id)
                    if old_school:
                        NotificationService.notify_school_updated(
                            school_id=old_school_id,
                            updated_by_name=current_user.name,
                            changes=f"• Administrator '{admin.name}' has been reassigned to another school."
                        )
                
                # Notify new school admins
                if new_school_id:
                    new_school = School.query.get(new_school_id)
                    if new_school:
                        NotificationService.notify_school_updated(
                            school_id=new_school_id,
                            updated_by_name=current_user.name,
                            changes=f"• New administrator '{admin.name}' has been assigned to your school."
                        )
            
            flash('Admin updated successfully!', 'success')
            return redirect(url_for('super_admin.admins'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating admin: {str(e)}', 'danger')
    schools = School.query.all()
    return render_template('super_admin/edit_admin.html', admin=admin, schools=schools)

@bp.route('/admins/<int:admin_id>/delete', methods=['POST'])
@login_required
def delete_admin(admin_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    admin = User.query.filter_by(id=admin_id, role='admin').first_or_404()
    
    # Store admin info for logging before deletion
    admin_name = admin.name
    admin_email = admin.email
    school_id = admin.school_id
    school_name = admin.school.name if admin.school else "no school"
    
    try:
        # First, delete all notifications associated with this admin
        from app.models.notification import Notification
        Notification.query.filter_by(recipient_id=admin_id).delete()
        
        # Delete all user activities associated with this admin
        from app.models.user_activity import UserActivity
        UserActivity.query.filter_by(user_id=admin_id).delete()
        
        # Then delete the admin user
        db.session.delete(admin)
        db.session.commit()
        
        # Notify other admins in the same school about the removal
        if school_id:
            from app.services.notification_service import NotificationService
            NotificationService.notify_admin_admin_removed(
                school_id=school_id,
                removed_admin_name=admin_name,
                removed_by_name=current_user.name
            )
        
        # Log the deletion activity
        log_activity(current_user.id, 'delete_admin', f'Deleted admin {admin_name} ({admin_email}) from {school_name}', request.remote_addr)
        flash('Admin deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting admin: {str(e)}', 'danger')
    return redirect(url_for('super_admin.admins'))

# --- STUDENT MANAGEMENT ---
@bp.route('/students')
@login_required
def students():
    log_activity(current_user.id, 'view_students', 'Accessed students management page', request.remote_addr)
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    search_query = request.args.get('search_query', '').strip()
    school_id = request.args.get('school_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Number of students per page
    
    # Get all schools for the filter dropdown
    schools = School.query.all()
    schools_count = len(schools)
    
    # Build the query
    query = Student.query.join(School, Student.school_id == School.id)
    
    if school_id:
        query = query.filter(Student.school_id == school_id)
    
    if search_query:
        # Use LIKE for MySQL (case-insensitive by default with utf8mb4_ci collation)
        query = query.filter(Student.name.like(f'%{search_query}%'))
    
    # Get all students (no pagination for grouped view)
    students = query.all()
    
    # Group students by school for better organization (include school id and name)
    students_by_school = {}
    for student in students:
        school_id = student.school.id if student.school else 0
        school_name = student.school.name if student.school else 'No School'
        if school_id not in students_by_school:
            students_by_school[school_id] = {'name': school_name, 'students': []}
        students_by_school[school_id]['students'].append(student)
    
    # Ensure schools with zero students are also listed
    for school in schools:
        if school.id not in students_by_school:
            students_by_school[school.id] = {'name': school.name, 'students': []}
    
    # Stats
    total_students = Student.query.count()
    active_students = Student.query.count()  # Assuming all students are active for now
    
    return render_template('super_admin/students.html', 
                         students_by_school=students_by_school,
                         schools=schools, 
                         schools_count=schools_count,
                         total_students=total_students,
                         active_students=active_students,
                         search_query=search_query, 
                         selected_school_id=school_id)

@bp.route('/students/<int:student_id>/view')
@login_required
def view_student(student_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.get_or_404(student_id)
    log_activity(current_user.id, 'view_student', f'Viewed student {student.name} profile', request.remote_addr)
    
    return render_template('student/view.html', student=student)

@bp.route('/students/create', methods=['GET', 'POST'])
@login_required
def create_student():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        age = int(request.form.get('age')) if request.form.get('age') else None
        gender = request.form.get('gender')
        height = float(request.form.get('height')) if request.form.get('height') else None
        weight = float(request.form.get('weight')) if request.form.get('weight') else None
        school_id = request.form.get('school_id')
        section_id = request.form.get('section_id')
        
        # Calculate birth_date from age if provided
        birth_date = None
        if age:
            from datetime import date
            current_year = date.today().year
            birth_date = date(current_year - age, 1, 1)  # Approximate birth date
        
        # Create user account for student
        password = request.form.get('password')
        user = User(name=name, email=email, role='student')
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.flush()  # Get the user ID
            
            # Create student
            student = Student(
                name=name,
                birth_date=birth_date,
                gender=gender,
                height=height,
                weight=weight,
                school_id=int(school_id) if school_id else None,
                section_id=int(section_id) if section_id else None,
                user_id=user.id,
                registered_by=current_user.id
            )
            
            # Calculate BMI if height and weight are provided
            if height and weight:
                height_m = height / 100  # Convert cm to meters
                student.bmi = round(weight / (height_m ** 2), 2)
            
            db.session.add(student)
            db.session.commit()
            
            # Send notification to student
            NotificationService.notify_account_created(
                user_id=user.id,
                password=password,
                created_by_name=current_user.name
            )
            
            # Send welcome email to student
            try:
                school = School.query.get(school_id) if school_id else None
                EmailService.send_welcome_email_student(
                    student_email=user.email,
                    student_name=user.name,
                    password=password,
                    school_name=school.name if school else None,
                    created_by_name=current_user.name
                )
            except Exception as e:
                current_app.logger.error(f"Failed to send welcome email to student {user.email}: {str(e)}")
            
            # Notify admins of the school about new student
            if school_id:
                NotificationService.notify_admin_student_operation(
                    school_id=int(school_id),
                    operation='created',
                    student_name=name,
                    performed_by_name=current_user.name
                )
            
            log_activity(current_user.id, 'create_student', f'Created student {name}', request.remote_addr)
            flash('Student created successfully!', 'success')
            return redirect(url_for('super_admin.students'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating student: {str(e)}', 'danger')
    
    schools = School.query.all()
    sections = Section.query.all()
    return render_template('super_admin/create_student.html', schools=schools, sections=sections)

@bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.get_or_404(student_id)
    
    if request.method == 'POST':
        # Track old values BEFORE making changes
        old_school_id = student.school_id
        old_name = student.name
        old_height = student.height
        old_weight = student.weight
        
        student.name = request.form.get('name')
        
        # Handle age by converting to birth_date
        age = int(request.form.get('age')) if request.form.get('age') else None
        if age:
            from datetime import date
            current_year = date.today().year
            student.birth_date = date(current_year - age, 1, 1)  # Approximate birth date
        
        student.gender = request.form.get('gender')
        student.height = float(request.form.get('height')) if request.form.get('height') else None
        student.weight = float(request.form.get('weight')) if request.form.get('weight') else None
        
        # Calculate BMI if height and weight are provided
        if student.height and student.weight:
            height_m = student.height / 100  # Convert cm to meters
            student.bmi = round(student.weight / (height_m ** 2), 2)
        
        # Update school and section
        school_id = request.form.get('school_id')
        section_id = request.form.get('section_id')
        
        if school_id:
            student.school_id = int(school_id)
        if section_id:
            student.section_id = int(section_id)
        
        try:
            
            db.session.commit()
            
            # Track changes for notifications
            changes = []
            new_school_id = int(school_id) if school_id else old_school_id
            
            if student.name != old_name:
                changes.append(f"• Name: {old_name} → {student.name}")
            if age:
                changes.append("• Age updated")
            if student.height != old_height:
                old_h = f"{old_height} cm" if old_height else "N/A"
                new_h = f"{student.height} cm" if student.height else "N/A"
                changes.append(f"• Height: {old_h} → {new_h}")
            if student.weight != old_weight:
                old_w = f"{old_weight} kg" if old_weight else "N/A"
                new_w = f"{student.weight} kg" if student.weight else "N/A"
                changes.append(f"• Weight: {old_w} → {new_w}")
            if new_school_id != old_school_id:
                old_school = School.query.get(old_school_id) if old_school_id else None
                new_school = School.query.get(new_school_id) if new_school_id else None
                changes.append(f"• School: {old_school.name if old_school else 'N/A'} → {new_school.name if new_school else 'N/A'}")
            
            # Send notification to student
            if changes:
                NotificationService.notify_student_updated(
                    student_id=student.id,
                    updated_by_name=current_user.name,
                    changes="\n".join(changes)
                )
            
            # Notify admins of the school about student update
            # Notify both old and new school if school was changed
            if new_school_id != old_school_id:
                # Notify old school admins
                if old_school_id:
                    NotificationService.notify_admin_student_operation(
                        school_id=old_school_id,
                        operation='updated',
                        student_name=student.name,
                        performed_by_name=current_user.name,
                        details=f"Student moved to another school.\n" + "\n".join(changes) if changes else "Student moved to another school."
                    )
                # Notify new school admins
                if new_school_id:
                    NotificationService.notify_admin_student_operation(
                        school_id=new_school_id,
                        operation='updated',
                        student_name=student.name,
                        performed_by_name=current_user.name,
                        details="\n".join(changes) if changes else None
                    )
            elif new_school_id:
                # Only notify if school didn't change
                NotificationService.notify_admin_student_operation(
                    school_id=new_school_id,
                    operation='updated',
                    student_name=student.name,
                    performed_by_name=current_user.name,
                    details="\n".join(changes) if changes else None
                )
            
            log_activity(current_user.id, 'edit_student', f'Updated student {student.name} profile information', request.remote_addr)
            flash('Student updated successfully!', 'success')
            return redirect(url_for('super_admin.students'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating student: {str(e)}', 'danger')
    
    schools = School.query.all()
    sections = Section.query.filter_by(school_id=student.school_id).all() if student.school_id else []
    
    return render_template('super_admin/edit_student.html', 
                         student=student, 
                         schools=schools, 
                         sections=sections)

@bp.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.get_or_404(student_id)
    
    try:
        # Store student details before deletion
        student_name = student.name
        school_id = student.school_id
        school_name = student.school.name if student.school else "unknown school"
        
        # Delete associated user account if exists
        if student.user:
            # First, delete all notifications associated with this student's user account
            from app.models.notification import Notification
            Notification.query.filter_by(recipient_id=student.user.id).delete()
            
            # Delete all user activities associated with this student's user account
            from app.models.user_activity import UserActivity
            UserActivity.query.filter_by(user_id=student.user.id).delete()
            db.session.delete(student.user)
        
        db.session.delete(student)
        db.session.commit()
        
        # Notify admins of the school about student deletion
        if school_id:
            from app.services.notification_service import NotificationService
            NotificationService.notify_admin_student_operation(
                school_id=school_id,
                operation='deleted',
                student_name=student_name,
                performed_by_name=current_user.name
            )
        
        log_activity(current_user.id, 'delete_student', f'Deleted student {student_name} from {school_name}', request.remote_addr)
        flash('Student deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting student: {str(e)}', 'danger')
    
    return redirect(url_for('super_admin.students'))

@bp.route('/reports')
@login_required
def reports():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    log_activity(current_user.id, 'view_reports', 'Accessed reports dashboard', request.remote_addr)
    
    # Get report notifications sent to super admins
    from app.models.notification import Notification
    admin_id = request.args.get('admin_id', type=int)
    
    # Get all report notifications
    reports_query = Notification.query.filter_by(
        notification_type='report_generated'
    ).order_by(Notification.created_at.desc())
    
    # Filter by admin if specified
    if admin_id:
        # Get the admin's school to filter notifications
        admin = User.query.get(admin_id)
        if admin and admin.school_id:
            reports_query = reports_query.filter_by(related_entity_id=admin.school_id)
    
    reports = reports_query.all()
    
    # Get admin and school data for display
    admins = {u.id: u for u in User.query.filter_by(role='admin').all()}
    schools = {s.id: s for s in School.query.all()}
    
    # Create a mapping of reports with additional data
    report_data = []
    for report in reports:
        school = schools.get(report.related_entity_id) if report.related_entity_id else None
        admin = None
        student_count = 0
        
        if school:
            # Find the admin for this school
            admin = next((a for a in admins.values() if a.school_id == school.id), None)
            # Get student count for this school
            student_count = Student.query.filter_by(school_id=school.id).count()
        
        report_data.append({
            'notification': report,
            'admin': admin,
            'school': school,
            'student_count': student_count
        })
    
    return render_template('super_admin/reports.html', 
                         reports=report_data, 
                         admins=admins, 
                         schools=schools, 
                         selected_admin_id=admin_id) 

@bp.route('/reports/<int:notification_id>/view')
@login_required
def view_report_details(notification_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    from app.models.notification import Notification
    notification = Notification.query.get_or_404(notification_id)
    
    # Get school and admin details
    school = School.query.get(notification.related_entity_id) if notification.related_entity_id else None
    admin = None
    students = []
    
    if school:
        admin = User.query.filter_by(school_id=school.id, role='admin').first()
        students = Student.query.filter_by(school_id=school.id).all()
    
    # Mark as read if not already
    if not notification.is_read:
        notification.mark_as_read()
    
    log_activity(current_user.id, 'view_report_details', f'Viewed report details for notification {notification_id}', request.remote_addr)
    
    return render_template('super_admin/view_report_details.html', 
                         notification=notification, 
                         admin=admin, 
                         school=school, 
                         students=students)

@bp.route('/reports/<int:notification_id>/mark-read', methods=['POST'])
@login_required
def mark_report_read(notification_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('super_admin.reports'))
    
    from app.models.notification import Notification
    notification = Notification.query.get_or_404(notification_id)
    
    try:
        notification.mark_as_read()
        log_activity(current_user.id, 'mark_report_read', f'Marked report notification {notification_id} as read', request.remote_addr)
        flash('Report marked as read!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error marking report as read: {str(e)}', 'danger')
    
    return redirect(url_for('super_admin.reports'))

@bp.route('/reports/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_report_notification(notification_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('super_admin.reports'))
    
    from app.models.notification import Notification
    notification = Notification.query.get_or_404(notification_id)
    
    try:
        # Store notification details for logging before deletion
        notification_title = notification.title
        school_id = notification.related_entity_id
        school_name = "Unknown School"
        
        if school_id:
            school = School.query.get(school_id)
            if school:
                school_name = school.name
        
        # Delete the notification
        db.session.delete(notification)
        db.session.commit()
        
        log_activity(current_user.id, 'delete_report', f'Deleted report notification "{notification_title}" from {school_name}', request.remote_addr)
        flash('Report deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting report: {str(e)}', 'danger')
        log_activity(current_user.id, 'delete_report_error', f'Failed to delete report notification {notification_id}: {str(e)}', request.remote_addr)
    
    return redirect(url_for('super_admin.reports'))
    return redirect(url_for('super_admin.reports'))

# --- EXPORT SCHOOL REPORT FILES (SUPER ADMIN) ---
@bp.route('/reports/school/<int:school_id>/export')
@login_required
def export_school_excel(school_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))

    school = School.query.get_or_404(school_id)
    students = Student.query.filter_by(school_id=school_id).all()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Students')

    header = workbook.add_format({'bold': True, 'bg_color': '#667eea', 'font_color': 'white'})
    center = workbook.add_format({'align': 'center'})

    headers = ['Name', 'Section', 'Gender', 'Birthdate', 'Age', 'Height (cm)', 'Weight (kg)', 'BMI']
    for col, h in enumerate(headers):
        worksheet.write(0, col, h, header)

    row = 1
    for s in students:
        worksheet.write(row, 0, s.name or '')
        worksheet.write(row, 1, s.section.name if s.section else '')
        worksheet.write(row, 2, s.gender or '', center)
        worksheet.write(row, 3, s.birth_date.strftime('%Y-%m-%d') if s.birth_date else '', center)
        worksheet.write(row, 4, s.age if hasattr(s, 'age') and s.age is not None else '', center)
        worksheet.write(row, 5, s.height if s.height is not None else '', center)
        worksheet.write(row, 6, s.weight if s.weight is not None else '', center)
        worksheet.write(row, 7, s.bmi if s.bmi is not None else '', center)
        row += 1

    worksheet.set_column(0, 0, 28)
    worksheet.set_column(1, 1, 22)
    worksheet.set_column(2, 7, 14)

    workbook.close()
    output.seek(0)

    filename = f'{school.name.replace(" ", "_")}_students.xlsx'
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     download_name=filename, as_attachment=True)

@bp.route('/reports/school/<int:school_id>/export_pdf')
@login_required
def export_school_pdf(school_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))

    school = School.query.get_or_404(school_id)
    students = Student.query.filter_by(school_id=school_id).all()

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    flow = []

    flow.append(Paragraph(f'Student Report - {school.name}', styles['Title']))
    flow.append(Spacer(1, 12))

    data = [['Name', 'Section', 'Gender', 'Birthdate', 'Age', 'Height (cm)', 'Weight (kg)', 'BMI']]
    for s in students:
        data.append([
            s.name or '',
            s.section.name if s.section else '',
            s.gender or '',
            s.birth_date.strftime('%Y-%m-%d') if s.birth_date else '',
            s.age if hasattr(s, 'age') and s.age is not None else '',
            s.height if s.height is not None else '',
            s.weight if s.weight is not None else '',
            f'{s.bmi:.1f}' if s.bmi is not None else ''
        ])

    tbl = Table(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e9eefb')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('ALIGN', (2,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fafbff')]),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    flow.append(tbl)

    doc.build(flow)
    output.seek(0)

    filename = f'{school.name.replace(" ", "_")}_students.pdf'
    return send_file(output, mimetype='application/pdf', download_name=filename, as_attachment=True)
@bp.route('/schools')
@login_required
def schools():
    log_activity(current_user.id, 'view_schools', 'Accessed schools management page', request.remote_addr)
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    search_query = request.args.get('search_query', '').strip()
    schools_query = School.query
    
    if search_query:
        like = f"%{search_query}%"
        # Case-insensitive match on name or address
        schools_query = schools_query.filter(
            # Use LIKE for MySQL (case-insensitive by default with utf8mb4_ci collation)
            (School.name.like(like)) | (School.address.like(like))
        )
    
    schools = schools_query.all()
    return render_template('super_admin/schools.html', schools=schools, search_query=search_query)

@bp.route('/schools/create', methods=['GET', 'POST'])
@login_required
def create_school():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        contact_number = request.form.get('contact_number')
        email = request.form.get('email')
        
        # Check if school name already exists
        if School.query.filter_by(name=name).first():
            flash('School name already exists', 'danger')
            return render_template('super_admin/create_school.html')
        
        school = School(
            name=name,
            address=address,
            contact_number=contact_number,
            email=email
        )
        
        try:
            db.session.add(school)
            db.session.commit()
            log_activity(current_user.id, 'create_school', f'Created school {name} at {address}', request.remote_addr)
            flash('School created successfully!', 'success')
            return redirect(url_for('super_admin.schools'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating school: {str(e)}', 'danger')
    
    return render_template('super_admin/create_school.html')

@bp.route('/schools/<int:school_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_school(school_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    school = School.query.get_or_404(school_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        contact_number = request.form.get('contact_number')
        email = request.form.get('email')
        
        # Check if school name already exists (excluding current school)
        existing_school = School.query.filter(School.name == name, School.id != school_id).first()
        if existing_school:
            flash('School name already exists', 'danger')
            return render_template('super_admin/edit_school.html', school=school)
        
        # Track changes for notification
        changes = []
        if school.name != name:
            changes.append(f"• School Name: {school.name} → {name}")
        if school.address != address:
            changes.append(f"• Address: {school.address or 'N/A'} → {address or 'N/A'}")
        if school.contact_number != contact_number:
            changes.append(f"• Contact Number: {school.contact_number or 'N/A'} → {contact_number or 'N/A'}")
        if school.email != email:
            changes.append(f"• Email: {school.email or 'N/A'} → {email or 'N/A'}")
        
        school.name = name
        school.address = address
        school.contact_number = contact_number
        school.email = email
        
        try:
            db.session.commit()
            
            # Notify all admins of the school about the update
            from app.services.notification_service import NotificationService
            NotificationService.notify_school_updated(
                school_id=school_id,
                updated_by_name=current_user.name,
                changes='\n'.join(changes) if changes else None
            )
            
            log_activity(current_user.id, 'edit_school', f'Updated school {name} information', request.remote_addr)
            flash('School updated successfully!', 'success')
            return redirect(url_for('super_admin.schools'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating school: {str(e)}', 'danger')
    
    return render_template('super_admin/edit_school.html', school=school)

@bp.route('/schools/<int:school_id>/delete', methods=['POST'])
@login_required
def delete_school(school_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    school = School.query.get_or_404(school_id)
    
    # Check if school has associated admins or students
    admin_count = User.query.filter_by(school_id=school_id).count()
    student_count = Student.query.filter_by(school_id=school_id).count()
    
    if admin_count > 0 or student_count > 0:
        flash(f'Cannot delete school. It has {admin_count} administrators and {student_count} students associated with it.', 'danger')
        return redirect(url_for('super_admin.schools'))
    
    # Get admin IDs before deletion for notification
    admin_ids = [admin.id for admin in User.query.filter_by(role='admin', school_id=school_id).all()]
    school_name = school.name
    
    try:
        db.session.delete(school)
        db.session.commit()
        
        # Notify admins about school deletion
        if admin_ids:
            from app.services.notification_service import NotificationService
            NotificationService.notify_school_deleted(
                school_name=school_name,
                admin_ids=admin_ids,
                deleted_by_name=current_user.name
            )
        
        log_activity(current_user.id, 'delete_school', f'Deleted school {school_name} and all associated data', request.remote_addr)
        flash('School deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting school: {str(e)}', 'danger')
    
    return redirect(url_for('super_admin.schools'))

@bp.route('/generate_sbfp_report', methods=['POST'])
@login_required
def generate_sbfp_report():
    """Generate a descriptive analytics report showing SBFP beneficiaries per school"""
    if current_user.role != 'super_admin':
        return {'error': 'Unauthorized'}, 403
    
    try:
        # Get all schools with their beneficiary counts
        schools = School.query.all()
        report_data = []
        
        for school in schools:
            # Count students marked as beneficiaries (is_beneficiary = True)
            beneficiary_count = Student.query.filter_by(
                school_id=school.id,
                is_beneficiary=True
            ).count()
            
            total_students = Student.query.filter_by(school_id=school.id).count()
            
            report_data.append({
                'school_name': school.name,
                'total_students': total_students,
                'sbfp_beneficiaries': beneficiary_count,
                'beneficiary_percentage': round((beneficiary_count / total_students * 100) if total_students > 0 else 0, 2)
            })
        
        # Sort by beneficiary count descending
        report_data.sort(key=lambda x: x['sbfp_beneficiaries'], reverse=True)
        
        # Generate PDF
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        elements = []
        
        # Title
        styles = getSampleStyleSheet()
        title = Paragraph(
            "SBFP Beneficiaries Descriptive Analytics Report",
            styles['Title']
        )
        elements.append(title)
        elements.append(Spacer(1, 0.5 * cm))
        
        # Summary paragraph
        total_schools_count = len(schools)
        total_beneficiaries = sum([d['sbfp_beneficiaries'] for d in report_data])
        total_students_all = sum([d['total_students'] for d in report_data])
        overall_percentage = round((total_beneficiaries / total_students_all * 100) if total_students_all > 0 else 0, 2)
        
        # Generate report date
        report_date = datetime.now().strftime("%B %d, %Y")
        
        summary_text = Paragraph(
            f"<b>Report Generated:</b> {report_date}<br/><br/>"
            f"<b>Report Summary:</b> This descriptive analytics report shows the number of SBFP (School-Based Feeding Program) beneficiaries across {total_schools_count} registered schools.<br/><br/>"
            f"<b>Overall Statistics:</b><br/>"
            f"• Total Schools: {total_schools_count}<br/>"
            f"• Total Students: {total_students_all}<br/>"
            f"• Total SBFP Beneficiaries: {total_beneficiaries}<br/>"
            f"• Overall Beneficiary Rate: {overall_percentage}%<br/><br/>"
            f"This report provides a comprehensive breakdown of SBFP beneficiaries per school, enabling accurate tracking and monitoring of the feeding program coverage.",
            styles['Normal']
        )
        elements.append(summary_text)
        elements.append(Spacer(1, 0.5 * cm))
        
        # Create a style for school names that allows wrapping
        school_name_style = ParagraphStyle(
            'SchoolNameStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            leftIndent=0,
            rightIndent=0,
            alignment=0,  # Left align
            spaceBefore=0,
            spaceAfter=0
        )
        
        # Table header
        table_data = [
            [Paragraph('<b>School Name</b>', styles['Normal']), 
             Paragraph('<b>Total Students</b>', styles['Normal']), 
             Paragraph('<b>SBFP Beneficiaries</b>', styles['Normal']), 
             Paragraph('<b>Beneficiary %</b>', styles['Normal'])]
        ]
        
        # Add data rows with Paragraph objects for school names to enable wrapping
        for data in report_data:
            # Use Paragraph for school name to enable text wrapping
            school_name_para = Paragraph(data['school_name'], school_name_style)
            table_data.append([
                school_name_para,
                str(data['total_students']),
                str(data['sbfp_beneficiaries']),
                f"{data['beneficiary_percentage']}%"
            ])
        
        # Create table with better column widths - give more space to school name
        table = Table(table_data, colWidths=[9*cm, 2.5*cm, 3*cm, 2.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),  # School name left-aligned
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),  # Numbers center-aligned
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (1, 1), (-1, -1), 9),  # Smaller font for numbers
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Top align for wrapped text
        ]))
        elements.append(table)
        
        # Add footer note
        elements.append(Spacer(1, 0.5 * cm))
        footer_note = Paragraph(
            "<i>Note: This report is generated automatically by the NutriKid System. "
            "SBFP beneficiaries are students identified as requiring nutritional intervention based on their BMI status.</i>",
            styles['Normal']
        )
        elements.append(footer_note)
        
        # Build PDF
        doc.build(elements)
        pdf_buffer.seek(0)
        
        # Log activity
        log_activity(current_user.id, 'generated_report', 'Generated SBFP beneficiaries descriptive analytics report', request.remote_addr)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'SBFP_Beneficiaries_Report_{datetime.now().strftime("%Y%m%d")}.pdf'
        )
    
    except Exception as e:
        # Log full exception to server logs for debugging
        try:
            from app import app
            app.logger.exception(f"Error generating SBFP report: {str(e)}")
        except Exception:
            # Fallback to printing if logger unavailable
            print(f"Error generating SBFP report: {str(e)}")

        # Return JSON error so frontend can parse and display it
        return jsonify({'error': str(e)}), 500