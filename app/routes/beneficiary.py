from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from sqlalchemy import or_

bp = Blueprint('beneficiary', __name__, url_prefix='/beneficiary')

@bp.route('/')
@login_required
def index():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    from app.models.student import Student
    from app import db
    
    # Ensure all students have correct school_id (fix for legacy data)
    students_without_school = Student.query.filter(
        Student.school_id.is_(None),
        Student.section_id.isnot(None)
    ).all()
    for student in students_without_school:
        if student.section and student.section.school_id:
            student.school_id = student.section.school_id
            db.session.add(student)
    db.session.commit()
    
    # Show all students marked as beneficiaries from the admin's school
    # If school_id is not set, fallback to students registered by this admin
    if current_user.school_id:
        beneficiaries = Student.query.filter(
            Student.school_id == current_user.school_id,
            Student.is_beneficiary == True
        ).order_by(Student.name).all()
    else:
        # Fallback: show beneficiaries registered by this admin if no school_id
        beneficiaries = Student.query.filter(
            Student.registered_by == current_user.id,
            Student.is_beneficiary == True
        ).order_by(Student.name).all()
    
    # Debug: Log beneficiary count
    print(f"DEBUG: Found {len(beneficiaries)} beneficiaries for admin {current_user.id} (school_id: {current_user.school_id})")
    for b in beneficiaries:
        print(f"DEBUG: Beneficiary - ID: {b.id}, Name: {b.name}, is_beneficiary: {b.is_beneficiary}, school_id: {b.school_id}")
    
    return render_template('beneficiary/index.html', beneficiaries=beneficiaries)

@bp.route('/select-students')
@login_required
def select_students():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    from app.models.student import Student
    from app.models.section import Section
    from app import db
    
    # Get all students from the admin's school that are not already beneficiaries
    if current_user.school_id:
        available_students = Student.query.filter(
            Student.school_id == current_user.school_id,
            or_(Student.is_beneficiary == False, Student.is_beneficiary.is_(None))
        ).order_by(Student.name).all()
    else:
        # Fallback: show students registered by this admin if no school_id
        available_students = Student.query.filter(
            Student.registered_by == current_user.id,
            or_(Student.is_beneficiary == False, Student.is_beneficiary.is_(None))
        ).order_by(Student.name).all()
    
    # Group students by section for better organization
    students_by_section = {}
    for student in available_students:
        section_name = student.section.name if student.section else "No Section"
        if section_name not in students_by_section:
            students_by_section[section_name] = []
        students_by_section[section_name].append(student)
    
    return render_template('beneficiary/select_students.html', 
                         students_by_section=students_by_section,
                         total_available=len(available_students))

@bp.route('/add-selected', methods=['POST'])
@login_required
def add_selected():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    from app.models.student import Student
    from app import db
    
    selected_student_ids = request.form.getlist('selected_students')
    
    if not selected_student_ids:
        flash('Please select at least one student to add as beneficiary.', 'warning')
        return redirect(url_for('beneficiary.select_students'))
    
    try:
        added_count = 0
        for student_id in selected_student_ids:
            student = Student.query.get(student_id)
            # Allow admin to add any student from their school
            if student:
                # Check if student belongs to admin's school
                if current_user.school_id:
                    if student.school_id == current_user.school_id:
                        # Set flag to prevent automatic BMI-based beneficiary update
                        setattr(student, '_skip_beneficiary_update', True)
                        # Set is_beneficiary to True - this will be preserved by the event listener
                        student.is_beneficiary = True
                        db.session.add(student)
                        added_count += 1
                else:
                    # Fallback: allow if admin registered the student
                    if student.registered_by == current_user.id:
                        # Set flag to prevent automatic BMI-based beneficiary update
                        setattr(student, '_skip_beneficiary_update', True)
                        # Set is_beneficiary to True - this will be preserved by the event listener
                        student.is_beneficiary = True
                        db.session.add(student)
                        added_count += 1
        
        db.session.commit()
        
        # Refresh the session to ensure we have the latest data
        db.session.expire_all()
        
        if added_count > 0:
            flash(f'Successfully added {added_count} student(s) to beneficiary list!', 'success')
        else:
            flash('No students were added. Please verify the students belong to your school.', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding students: {str(e)}', 'danger')
    
    return redirect(url_for('beneficiary.index'))

@bp.route('/remove-from-beneficiary/<int:student_id>', methods=['POST'])
@login_required
def remove_from_beneficiary(student_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    from app.models.student import Student
    from app import db
    
    student = Student.query.get_or_404(student_id)
    
    # Check if student belongs to admin's school
    if current_user.school_id:
        if student.school_id != current_user.school_id:
            flash('You can only modify students from your school', 'danger')
            return redirect(url_for('beneficiary.index'))
    else:
        # Fallback: check if admin registered this student
        if student.registered_by != current_user.id:
            flash('You can only modify students you registered', 'danger')
            return redirect(url_for('beneficiary.index'))
    
    try:
        # Remove from beneficiary list (don't delete the student)
        student.is_beneficiary = False
        # Set flag to prevent automatic beneficiary recalculation based on BMI
        student._skip_beneficiary_update = True
        db.session.add(student)
        db.session.commit()
        
        flash(f'Success! Student "{student.name}" has been removed from beneficiary list!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing student from beneficiary list: {str(e)}', 'danger')
    
    return redirect(url_for('beneficiary.index'))

@bp.route('/remove/<int:student_id>', methods=['POST'])
@login_required
def remove(student_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    from app.models.student import Student
    from app.models.user import User
    from app import db
    
    student = Student.query.get_or_404(student_id)
    
    # Check if student belongs to admin's school
    if current_user.school_id:
        if student.school_id != current_user.school_id:
            flash('You can only remove students from your school', 'danger')
            return redirect(url_for('beneficiary.index'))
    else:
        # Fallback: check if admin registered this student
        if student.registered_by != current_user.id:
            flash('You can only remove students you registered', 'danger')
            return redirect(url_for('beneficiary.index'))
    
    try:
        # Delete associated user account if exists
        if student.user_id:
            user = User.query.get(student.user_id)
            if user:
                # First, delete all user activities associated with this user
                from app.models.user_activity import UserActivity
                UserActivity.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
        
        # Delete student record
        student_name = student.name
        db.session.delete(student)
        db.session.commit()
        
        flash(f'Student "{student_name}" has been removed successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing student: {str(e)}', 'danger')
    
    return redirect(url_for('beneficiary.index')) 