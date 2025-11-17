from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app import db
from app.models.section import Section
from app.models.grade_level import GradeLevel
from app.models.student import Student
from app.models.user import User
from app.models.school import School
from app.models.user_activity import UserActivity
import random
import string
from datetime import datetime
from app.services.notification_service import NotificationService

def log_activity(user_id, activity_type, description, ip_address=None):
    activity = UserActivity(user_id=user_id, activity_type=activity_type, description=description, ip_address=ip_address)
    db.session.add(activity)
    db.session.commit()

bp = Blueprint('section', __name__, url_prefix='/section')

@bp.route('/')
@login_required
def index():
    log_activity(current_user.id, 'view_sections', 'Accessed sections management page', request.remote_addr)
    if current_user.role not in ['super_admin', 'admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    if current_user.role == 'super_admin':
        grade_levels = GradeLevel.query.all()
    else:
        grade_levels = GradeLevel.query.filter_by(school_id=current_user.school_id).all()
    return render_template('section/index.html', grade_levels=grade_levels)

@bp.route('/grade/create', methods=['GET', 'POST'])
@login_required
def create_grade():
    if current_user.role not in ['super_admin', 'admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name')
        school_id = request.form.get('school_id')
        if current_user.role == 'admin':
            school_id = current_user.school_id
        grade = GradeLevel(name=name, school_id=school_id)
        db.session.add(grade)
        db.session.commit()
        
        # Send notification about grade creation
        try:
            NotificationService.notify_grade_changes(
                grade_id=grade.id,
                action='created',
                performed_by_name=current_user.name
            )
        except Exception as e:
            current_app.logger.error(f"Error sending grade creation notification: {str(e)}")
        
        flash('Grade level created successfully!', 'success')
        return redirect(url_for('section.index'))
    schools = School.query.all() if current_user.role == 'super_admin' else None
    return render_template('section/create_grade.html', schools=schools)

@bp.route('/grade/<int:grade_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_grade(grade_id):
    grade = GradeLevel.query.get_or_404(grade_id)
    if current_user.role == 'admin' and grade.school_id != current_user.school_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    if request.method == 'POST':
        grade.name = request.form.get('name')
        db.session.commit()
        
        # Send notification about grade update
        try:
            NotificationService.notify_grade_changes(
                grade_id=grade.id,
                action='updated',
                performed_by_name=current_user.name
            )
        except Exception as e:
            current_app.logger.error(f"Error sending grade update notification: {str(e)}")
        
        flash('Grade level updated successfully!', 'success')
        return redirect(url_for('section.index'))
    return render_template('section/edit_grade.html', grade=grade)

@bp.route('/grade/<int:grade_id>/delete', methods=['POST'])
@login_required
def delete_grade(grade_id):
    grade = GradeLevel.query.get_or_404(grade_id)
    if current_user.role == 'admin' and grade.school_id != current_user.school_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    # Store grade info for logging
    grade_name = grade.name
    
    try:
        # Import Notification model and text for raw SQL
        from app.models.notification import Notification
        from sqlalchemy import text
        
        # Get all sections in this grade level
        sections_in_grade = Section.query.filter_by(grade_level_id=grade_id).all()
        total_students_deleted = 0
        user_ids_to_delete = []
        
        # Collect all user IDs that will be deleted
        for section in sections_in_grade:
            students_in_section = Student.query.filter_by(section_id=section.id).all()
            for student in students_in_section:
                if student.user:
                    user_ids_to_delete.append(student.user.id)
        
        # Delete notifications for these users BEFORE deleting users
        # This prevents the foreign key constraint error
        if user_ids_to_delete:
            # Delete notifications using raw SQL to avoid ORM cascade issues
            db.session.execute(
                text("DELETE FROM notifications WHERE recipient_id IN :user_ids"),
                {"user_ids": tuple(user_ids_to_delete)}
            )
            # Commit the notification deletion immediately to prevent autoflush issues
            db.session.commit()
        
        # Use no_autoflush to prevent premature flushes during deletion
        with db.session.no_autoflush:
            # Now delete all sections and their students
            for section in sections_in_grade:
                students_in_section = Student.query.filter_by(section_id=section.id).all()
                
                # Delete students and their user accounts
                for student in students_in_section:
                    if student.user:
                        # Delete user activities first
                        UserActivity.query.filter_by(user_id=student.user.id).delete()
                        # Delete user account (notifications already deleted above)
                        db.session.delete(student.user)
                    # Delete student record
                    db.session.delete(student)
                    total_students_deleted += 1
                
                # Delete the section
                db.session.delete(section)
            
            # Delete the grade level
            db.session.delete(grade)
        
        # Commit all remaining changes at once
        db.session.commit()
        
        log_activity(current_user.id, 'delete_grade', f'Deleted grade level: {grade_name} (removed {len(sections_in_grade)} sections and {total_students_deleted} students)', request.remote_addr)
        
        if total_students_deleted > 0:
            flash(f'Grade level "{grade_name}" deleted successfully! Removed {len(sections_in_grade)} sections and {total_students_deleted} students.', 'success')
        else:
            flash(f'Grade level "{grade_name}" deleted successfully!', 'success')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting grade level: {str(e)}', 'danger')
    
    return redirect(url_for('section.index'))

@bp.route('/grade/<int:grade_id>/sections')
@login_required
def grade_sections(grade_id):
    grade = GradeLevel.query.get_or_404(grade_id)
    if current_user.role == 'admin' and grade.school_id != current_user.school_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    sections = Section.query.filter_by(grade_level_id=grade_id).all()
    return render_template('section/sections.html', grade=grade, sections=sections)

@bp.route('/grade/<int:grade_id>/sections/create', methods=['GET', 'POST'])
@login_required
def create_section(grade_id):
    grade = GradeLevel.query.get_or_404(grade_id)
    if current_user.role == 'admin' and grade.school_id != current_user.school_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name')
        section = Section(name=name, grade_level_id=grade_id, school_id=grade.school_id)
        db.session.add(section)
        db.session.commit()
        
        # Send notification about section creation
        try:
            NotificationService.notify_section_changes(
                section_id=section.id,
                action='created',
                performed_by_name=current_user.name
            )
        except Exception as e:
            current_app.logger.error(f"Error sending section creation notification: {str(e)}")
        
        flash('Section created successfully!', 'success')
        return redirect(url_for('section.grade_sections', grade_id=grade_id))
    return render_template('section/create_section.html', grade=grade)

@bp.route('/sections/<int:section_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_section(section_id):
    section = Section.query.get_or_404(section_id)
    grade = section.grade_level_obj
    if current_user.role == 'admin' and section.school_id != current_user.school_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    if request.method == 'POST':
        section.name = request.form.get('name')
        db.session.commit()
        
        # Send notification about section update
        NotificationService.notify_section_changes(
            section_id=section.id,
            action='updated',
            performed_by_name=current_user.name
        )
        
        flash('Section updated successfully!', 'success')
        return redirect(url_for('section.grade_sections', grade_id=grade.id))
    return render_template('section/edit_section.html', section=section, grade=grade)

@bp.route('/sections/<int:section_id>/delete', methods=['POST'])
@login_required
def delete_section(section_id):
    section = Section.query.get_or_404(section_id)
    grade = section.grade_level_obj
    if current_user.role == 'admin' and section.school_id != current_user.school_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    # Store section info for logging
    section_name = section.name
    grade_name = grade.name
    
    try:
        # Import Notification model and text for raw SQL
        from app.models.notification import Notification
        from sqlalchemy import text
        
        # Check if there are students in this section
        students_in_section = Student.query.filter_by(section_id=section_id).all()
        
        if students_in_section:
            # Collect user IDs that will be deleted
            user_ids_to_delete = []
            for student in students_in_section:
                if student.user:
                    user_ids_to_delete.append(student.user.id)
            
            # Delete notifications for these users BEFORE deleting users
            # This prevents the foreign key constraint error
            if user_ids_to_delete:
                db.session.execute(
                    text("DELETE FROM notifications WHERE recipient_id IN :user_ids"),
                    {"user_ids": tuple(user_ids_to_delete)}
                )
                # Commit the notification deletion immediately to prevent autoflush issues
                db.session.commit()
            
            # Use no_autoflush to prevent premature flushes during deletion
            with db.session.no_autoflush:
                # Delete all students and their associated user accounts
                for student in students_in_section:
                    if student.user:
                        # Delete user activities first
                        UserActivity.query.filter_by(user_id=student.user.id).delete()
                        # Delete user account (notifications already deleted above)
                        db.session.delete(student.user)
                    # Delete student record
                    db.session.delete(student)
        
        # Delete the section
        db.session.delete(section)
        db.session.commit()
        
        log_activity(current_user.id, 'delete_section', f'Deleted section: {section_name} from {grade_name} (removed {len(students_in_section)} students)', request.remote_addr)
        
        if students_in_section:
            flash(f'Section "{section_name}" and {len(students_in_section)} students deleted successfully!', 'success')
        else:
            flash(f'Section "{section_name}" deleted successfully!', 'success')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting section: {str(e)}', 'danger')
    
    return redirect(url_for('section.grade_sections', grade_id=grade.id))

@bp.route('/sections/<int:section_id>/students')
@login_required
def students(section_id):
    section = Section.query.get_or_404(section_id)
    if current_user.role == 'admin' and section.school_id != current_user.school_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    return render_template('section/students.html', section=section)

@bp.route('/sections/<int:section_id>/add_student', methods=['GET', 'POST'])
@login_required
def add_student(section_id):
    section = Section.query.get_or_404(section_id)
    if current_user.role == 'admin' and section.school_id != current_user.school_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        preferences = request.form.get('preferences', '').strip()
        birth_date = request.form.get('birth_date')
        gender = request.form.get('gender')
        height = request.form.get('height')
        weight = request.form.get('weight')
        
        # Basic validation
        if not name or not email:
            flash('Name and email are required fields.', 'danger')
            return render_template('section/add_student.html', section=section)
        
        # Check for duplicate email
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists. Please use a different email address.', 'danger')
            return render_template('section/add_student.html', section=section)
        
        try:
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            user = User(name=name, email=email, role='student', school_id=section.school_id)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            
            student = Student(
                user_id=user.id,
                section_id=section_id,
                name=name,
                birth_date=datetime.strptime(birth_date, '%Y-%m-%d').date() if birth_date else None,
                gender=gender,
                height=float(height) if height else None,
                weight=float(weight) if weight else None,
                preferences=preferences,
                school_id=section.school_id,
                registered_by=current_user.id
            )
            student.calculate_bmi()
            db.session.add(student)
            
            db.session.commit()
            
            # Send notification about student addition
            NotificationService.notify_student_added(
                student_id=student.id,
                added_by_name=current_user.name
            )
            
            flash(f'Student added successfully! Password: {password}', 'success')
            return redirect(url_for('section.students', section_id=section_id))
            
        except Exception as e:
            db.session.rollback()
            if 'Duplicate entry' in str(e) and 'email' in str(e):
                flash('Email already exists. Please use a different email address.', 'danger')
            else:
                flash(f'Error creating student: {str(e)}', 'danger')
            return render_template('section/add_student.html', section=section)
    return render_template('section/add_student.html', section=section) 