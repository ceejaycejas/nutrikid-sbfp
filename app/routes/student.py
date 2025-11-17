from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.student import Student
from app.models.user import User
from app.models.section import Section
from app.models.school import School
from app.models.user_activity import UserActivity
from app.services.notification_service import NotificationService
from datetime import datetime
import random
import string

def log_activity(user_id, activity_type, description, ip_address=None):
    activity = UserActivity(user_id, activity_type, description, ip_address)
    db.session.add(activity)
    db.session.commit()

bp = Blueprint('student', __name__, url_prefix='/student')

@bp.route('/profile')
@login_required
def profile():
    log_activity(current_user.id, 'view_profile', 'Accessed student profile page', request.remote_addr)
    if current_user.role != 'student':
        log_activity(current_user.id, 'unauthorized_access', f'Attempted to access student profile as {current_user.role}', request.remote_addr)
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('student/profile.html', student=student)

@bp.route('/<int:student_id>')
@login_required
def view(student_id):
    student = Student.query.get_or_404(student_id)
    log_activity(current_user.id, 'view_student_detail', f'Viewed student profile: {student.name}', request.remote_addr)
    
    # Get referrer information to determine where to go back
    referrer = request.args.get('from', '')
    
    # Check if user is admin of the same school or the student themselves
    if current_user.role == 'admin':
        # Ensure student has school_id set (fix for legacy data)
        if not student.school_id and student.section and student.section.school_id:
            student.school_id = student.section.school_id
            from app import db
            db.session.add(student)
            db.session.commit()
        
        # Get student's school_id (check multiple sources)
        student_school_id = student.school_id
        if not student_school_id and student.section:
            student_school_id = student.section.school_id
        
        # Allow access if:
        # 1. Admin has school_id and student belongs to that school (primary check - via school_id or section)
        # 2. Admin registered the student (fallback for legacy data or when school_id is missing)
        can_view = False
        
        if current_user.school_id:
            # Primary check: student belongs to admin's school (via school_id)
            if student_school_id and student_school_id == current_user.school_id:
                can_view = True
            # Check via section if student doesn't have school_id set
            elif student.section and student.section.school_id == current_user.school_id:
                can_view = True
            # Fallback: allow if admin registered the student (for legacy data or edge cases)
            elif student.registered_by and student.registered_by == current_user.id:
                can_view = True
        else:
            # Admin has no school_id: allow if they registered the student
            if student.registered_by and student.registered_by == current_user.id:
                can_view = True
        
        if can_view:
            return render_template('student/view.html', student=student, referrer=referrer)
        else:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('school.dashboard'))
    elif current_user.role == 'student' and current_user.id == student.user_id:
        return render_template('student/view.html', student=student, referrer=referrer)
    elif current_user.role == 'super_admin':
        return render_template('student/view.html', student=student, referrer=referrer)
    
    flash('Unauthorized access', 'danger')
    return redirect(url_for('school.dashboard'))

@bp.route('/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(student_id):
    student = Student.query.get_or_404(student_id)
    # Check if user is admin of the same school
    if current_user.role != 'admin' or student.section.school_id != current_user.school_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    # Get referrer information
    referrer = request.args.get('from', '')
    
    if request.method == 'POST':
        # Store old data before updating
        old_data = {
            'name': student.name,
            'birth_date': student.birth_date,
            'gender': student.gender,
            'height': student.height,
            'weight': student.weight,
            'bmi': student.bmi,
            'section_id': student.section_id,
            'preferences': student.preferences
        }
        
        # Update student data
        student.name = request.form.get('name')
        birth_date_str = request.form.get('birth_date')
        if birth_date_str:
            student.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
        student.gender = request.form.get('gender')
        height_str = request.form.get('height')
        weight_str = request.form.get('weight')
        if height_str:
            student.height = float(height_str)
        if weight_str:
            student.weight = float(weight_str)
        student.calculate_bmi()
        
        # Update associated user account
        user = User.query.get(student.user_id)
        if user:
            user.name = student.name
            user.email = request.form.get('email')
        
        try:
            db.session.commit()
            log_activity(current_user.id, 'edit_student_profile', f'Updated student profile: {student.name}', request.remote_addr)
            
            # Send automatic notification about changes
            NotificationService.detect_and_notify_student_changes(
                student=student,
                old_data=old_data,
                updated_by_name=current_user.name
            )
            
            # Send email notification to super admins about data update
            try:
                from app.services.email_service import EmailService
                from flask import current_app
                super_admins = User.query.filter_by(role='super_admin').all()
                school = School.query.get(student.school_id) if student.school_id else None
                
                update_details = f"Updated student '{student.name}' (ID: {student.id})"
                if student.height and student.weight:
                    update_details += f" - Height: {student.height}cm, Weight: {student.weight}kg, BMI: {student.bmi:.2f if student.bmi else 'N/A'}"
                
                for sa in super_admins:
                    EmailService.send_admin_update_notification_to_super_admin(
                        super_admin_email=sa.email,
                        super_admin_name=sa.name,
                        admin_name=current_user.name,
                        school_name=school.name if school else 'Unknown School',
                        update_type='student_updated',
                        update_details=update_details
                    )
            except Exception as e:
                current_app.logger.error(f"Failed to send email notification about student update: {str(e)}")
            
            flash('Student information updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating student information: {str(e)}', 'danger')
        
        # Preserve referrer when redirecting back
        if referrer:
            return redirect(url_for('student.view', student_id=student.id) + f'?from={referrer}')
        else:
            return redirect(url_for('student.view', student_id=student.id))
    
    return render_template('student/edit.html', student=student, referrer=referrer)

@bp.route('/<int:student_id>/delete', methods=['POST'])
@login_required
def delete(student_id):
    student = Student.query.get_or_404(student_id)
    # Check if user is admin of the same school
    if current_user.role != 'admin' or student.section.school_id != current_user.school_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    section_id = student.section_id
    
    try:
        # Delete associated user account
        if student.user_id:
            user = User.query.get(student.user_id)
            if user:
                # First, delete all user activities associated with this user
                from app.models.user_activity import UserActivity
                UserActivity.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
        
        # Delete student record
        db.session.delete(student)
        db.session.commit()
        flash('Student has been deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting student: {str(e)}', 'danger')
    
    return redirect(url_for('section.students', section_id=section_id))

@bp.route('/update_info', methods=['POST'])
@login_required
def update_info():
    if current_user.role != 'student':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if student:
        # Store old data
        old_data = {
            'height': student.height,
            'weight': student.weight,
            'bmi': student.bmi
        }
        
        # Update health metrics
        height_str = request.form.get('height')
        weight_str = request.form.get('weight')
        if height_str:
            student.height = float(height_str)
        if weight_str:
            student.weight = float(weight_str)
        student.calculate_bmi()
        
        try:
            db.session.commit()
            log_activity(current_user.id, 'update_health_info', f'Updated height and weight - BMI: {student.bmi:.1f}', request.remote_addr)
            
            # Send automatic notification about self-update
            NotificationService.detect_and_notify_student_changes(
                student=student,
                old_data=old_data,
                updated_by_name="yourself"
            )
            
            flash('Your information has been updated successfully!', 'success')
        except:
            db.session.rollback()
            flash('Error updating information', 'danger')
    
    return redirect(url_for('school.dashboard'))

@bp.route('/<int:student_id>/reset_password', methods=['POST'])
@login_required
def reset_password(student_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.get_or_404(student_id)
    if student.user:
        # Generate new random password
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        student.user.set_password(new_password)
        
        try:
            db.session.commit()
            log_activity(current_user.id, 'reset_student_password', f'Reset password for student: {student.name}', request.remote_addr)
            
            # Notify student about password reset
            NotificationService.notify_password_changed(
                user_id=student.user.id,
                changed_by_name=current_user.name
            )
            
            flash(f'Password reset successful! New password: {new_password}', 'success')
        except:
            db.session.rollback()
            flash('Error resetting password', 'danger')
    
    return redirect(url_for('student.view', student_id=student.id))