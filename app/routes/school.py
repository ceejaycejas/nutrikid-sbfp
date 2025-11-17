from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app import db
from app.models.section import Section
from app.models.student import Student
from app.models.school import School
from app.models.user import User
from app.models.grade_level import GradeLevel
from app.models.user_activity import UserActivity
from datetime import datetime, timedelta
from app.services.notification_service import NotificationService
from sqlalchemy import text, inspect
import calendar
import traceback

bp = Blueprint('school', __name__, url_prefix='/school')

def log_activity(user_id, activity_type, description, ip_address=None):
    try:
        if user_id:  # Only log if user is authenticated
            activity = UserActivity(user_id=user_id, activity_type=activity_type, description=description, ip_address=ip_address)
            db.session.add(activity)
            db.session.commit()
    except Exception as e:
        print(f"Error logging activity: {str(e)}")

@bp.route('/')
@login_required
def index():
    if current_user.role not in ['super_admin', 'admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))

    # Optional search by school name (and address) from the new search bar
    search_query = request.args.get('search_query', '').strip()
    if current_user.role == 'super_admin':
        query = School.query
        if search_query:
            like = f"%{search_query}%"
            # Use LIKE for MySQL (case-insensitive by default with utf8mb4_ci collation)
            query = query.filter((School.name.like(like)) | (School.address.like(like)))
        schools = query.all()
    else:
        # Admins only see their own school; honor search if provided
        if not current_user.school:
            schools = []
        else:
            school = current_user.school
            if search_query:
                q = search_query.lower()
                if (q in (school.name or '').lower()) or (q in (school.address or '').lower()):
                    schools = [school]
                else:
                    schools = []
            else:
                schools = [school]
    
    return render_template('school/index.html', schools=schools)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        contact_number = request.form.get('contact_number')
        
        # Check if school name already exists
        if School.query.filter_by(name=name).first():
            flash('School name already exists', 'danger')
            return render_template('school/create.html')
        
        # Fix: Create School instance and set attributes separately
        school = School()
        school.name = name
        school.address = address
        school.contact_number = contact_number
        db.session.add(school)
        db.session.commit()
        
        flash('School created successfully!', 'success')
        return redirect(url_for('school.index'))
    
    return render_template('school/create.html')

@bp.route('/<int:school_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(school_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    school = School.query.get_or_404(school_id)
    
    if request.method == 'POST':
        # Fix: Set attributes separately instead of passing as constructor params
        school.name = request.form.get('name')
        school.address = request.form.get('address')
        school.contact_number = request.form.get('contact_number')
        db.session.commit()
        
        flash('School updated successfully!', 'success')
        return redirect(url_for('school.index'))
    
    return render_template('school/edit.html', school=school)

@bp.route('/<int:school_id>/delete', methods=['POST'])
@login_required
def delete(school_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    try:
        school = School.query.get_or_404(school_id)
        school_name = school.name
        
        # Delete all related records first to avoid foreign key constraint errors
        # Delete students associated with this school
        Student.query.filter_by(school_id=school_id).delete()

        # Delete sections associated with this school first (sections reference grade_level)
        Section.query.filter_by(school_id=school_id).delete()

        # Then delete grade levels associated with this school
        GradeLevel.query.filter_by(school_id=school_id).delete()
        
        # Delete users (admins) associated with this school
        # First remove related user_activity and notification rows that reference these users
        user_ids = [u.id for u in User.query.filter_by(school_id=school_id).all()]
        if user_ids:
            try:
                from app.models.notification import Notification
            except Exception:
                Notification = None

            # Fix: Use proper SQLAlchemy syntax for 'in' operator
            if user_ids:
                # Use raw SQL to avoid typing issues
                from sqlalchemy import text
                db.session.execute(
                    text("DELETE FROM user_activity WHERE user_id IN :user_ids"),
                    {"user_ids": tuple(user_ids)}
                )

                # Delete notifications sent to these users (if the model exists in the project)
                if Notification is not None:
                    # Use correct table name: 'notifications' (plural) not 'notification' (singular)
                    try:
                        # Check if notifications table exists before trying to delete
                        inspector = inspect(db.engine)
                        table_names = inspector.get_table_names()
                        
                        if 'notifications' in table_names:
                            db.session.execute(
                                text("DELETE FROM notifications WHERE recipient_id IN :user_ids"),
                                {"user_ids": tuple(user_ids)}
                            )
                            db.session.flush()  # Flush to ensure deletion happens
                        else:
                            current_app.logger.warning("Notifications table does not exist, skipping notification deletion")
                    except Exception as notif_error:
                        # If notifications table doesn't exist or deletion fails, log and continue
                        current_app.logger.warning(f"Could not delete notifications: {str(notif_error)}")
                        # Continue with deletion even if notifications table doesn't exist
                        db.session.rollback()  # Rollback only the notification deletion attempt

        # Now delete the user rows
        User.query.filter_by(school_id=school_id).delete(synchronize_session=False)
        
        # Now delete the school
        db.session.delete(school)
        db.session.commit()
        
        # Log the activity
        log_activity(current_user.id, 'delete_school', 
                    f'Deleted school {school_name} and all associated records', 
                    request.remote_addr)
        
        flash(f'School "{school_name}" and all associated data deleted successfully!', 'success')
        return redirect(url_for('school.index'))
        
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        print(f"Error deleting school: {error_msg}")
        print(f"Traceback: {traceback.format_exc()}")
        
        flash(f'Error deleting school: {error_msg}', 'danger')
        return redirect(url_for('school.index'))

@bp.route('/dashboard')
@login_required
def dashboard():
    try:
        # Log dashboard access
        log_activity(current_user.id, 'dashboard_access', f'Accessed dashboard as {current_user.role}', request.remote_addr)
        
        # Common activity statistics
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        recent_activities = UserActivity.query.filter(
            UserActivity.created_at >= seven_days_ago
        ).order_by(UserActivity.created_at.desc()).limit(15).all()
        
        recent_activity_count = UserActivity.query.filter(
            UserActivity.created_at >= twenty_four_hours_ago
        ).count()
        
        # Fix: Use proper SQLAlchemy syntax for filtering
        from sqlalchemy import and_, text
        today_logins = UserActivity.query.filter(
            and_(
                text("activity_type = 'login'"),
                UserActivity.created_at >= today_start
            )
        ).count()
        
        # Fix: Use proper SQLAlchemy syntax for 'in' operator with list
        today_failed_logins = UserActivity.query.filter(
            and_(
                text("activity_type IN ('login_failed', 'login_attempt')"),
                UserActivity.created_at >= today_start
            )
        ).count()
        
        if current_user.role == 'admin':
            return _get_admin_dashboard_data(
                recent_activities, recent_activity_count, today_logins, today_failed_logins
            )
        elif current_user.role == 'student':
            return _get_student_dashboard_data()
        elif current_user.role == 'super_admin':
            # Get school filter from request
            school_id = request.args.get('school_id', type=int)
            return _get_super_admin_dashboard_data(
                recent_activities, recent_activity_count, today_logins, today_failed_logins, school_id
            )
        else:
            flash('Invalid user role', 'danger')
            return redirect(url_for('auth.logout'))

    except Exception as e:
        # Log the error with more details
        error_details = traceback.format_exc()
        print(f"Dashboard error: {str(e)}\nTraceback: {error_details}")
        
        # Log the error to user activity
        try:
            log_activity(current_user.id if current_user.is_authenticated else None, 
                        'dashboard_error', f'Dashboard error: {str(e)}', request.remote_addr)
        except:
            pass  # Don't let logging errors crash the error handler
        
        flash('An error occurred while loading the dashboard. Please try again.', 'danger')
        
        # Get schools even in error case so dropdown works
        try:
            all_schools = School.query.order_by(School.name).all()
        except:
            all_schools = []
        
        # Return a safe fallback dashboard
        return render_template('dashboard/index.html', 
            total_schools=0,
            total_admins=0,
            total_students=0,
            total_sections=0,
            recent_activities=[],
            bmi_distribution={'normal': 0, 'underweight': 0, 'overweight': 0, 'obese': 0, 'wasted': 0, 'severely_wasted': 0},
            recent_activity_count=0,
            today_logins=0,
            today_failed_logins=0,
            # Safe defaults for admin-specific data
            total_beneficiaries=0,
            total_students_admin=0,
            improved_bmi_percent=0,
            feeding_compliance_percent=0,
            num_at_risk=0,
            at_risk_students=[],
            sections=[],
            bmi_progress={'labels': [], 'values': []},
            feeding_participation={'labels': [], 'values': []},
            avg_weight_gain={'sections': [], 'before': [], 'after': []},
            avg_height_gain={'sections': [], 'before': [], 'after': []},
            allergy_counts={'labels': [], 'values': []},
            # School filter data (even in error case)
            all_schools=all_schools,
            selected_school=None,
            selected_school_id=None
        )

def _get_admin_dashboard_data(recent_activities, recent_activity_count, today_logins, today_failed_logins):
    """Get dashboard data for admin users with proper error handling"""
    try:
        # Validate admin has school assigned
        if not current_user.school_id:
            flash('Your account is not assigned to a school. Please contact the super admin.', 'warning')
            return _render_safe_admin_dashboard(recent_activities, recent_activity_count, today_logins, today_failed_logins)
        
        # Get sections and students for admin's school with error handling
        try:
            sections = Section.query.filter_by(school_id=current_user.school_id).all()
            school_students = Student.query.filter_by(school_id=current_user.school_id).all()
            admin_students = Student.query.filter_by(registered_by=current_user.id).all()
        except Exception as db_error:
            print(f"Database query error: {str(db_error)}")
            return _render_safe_admin_dashboard(recent_activities, recent_activity_count, today_logins, today_failed_logins)
        
        # Calculate core metrics with validation
        total_sections = len(sections) if sections else 0
        total_students = len(school_students) if school_students else 0
        total_students_admin = len(admin_students) if admin_students else 0
        
        # Calculate BMI distribution for all students with BMI data
        bmi_distribution = _calculate_student_bmi_distribution(school_students)
        
        # Get beneficiary and at-risk students with validation
        try:
            beneficiary_students = _get_beneficiary_students(school_students)
        except Exception as e:
            print(f"Error getting beneficiary students: {str(e)}")
            beneficiary_students = []
            
        try:
            at_risk_students = _get_at_risk_students(school_students)
        except Exception as e:
            print(f"Error getting at-risk students: {str(e)}")
            at_risk_students = []
        
        total_beneficiaries = len(beneficiary_students)
        num_at_risk = len(at_risk_students)
        
        # Calculate analytics with improved accuracy and error handling
        try:
            dashboard_analytics = _calculate_dashboard_analytics(sections, school_students, beneficiary_students)
        except Exception as e:
            print(f"Error calculating dashboard analytics: {str(e)}")
            dashboard_analytics = {
                'bmi_progress': {'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], 'values': [18.5, 18.5, 18.5, 18.5, 18.5, 18.5]},
                'section_analytics': {'labels': [], 'total_students': [], 'beneficiaries': [], 'participation_rate': []},
                'nutritional_trends': {'labels': [], 'healthy': [], 'at_risk': []},
                'health_metrics': {'improved_count': 0, 'stable_count': 0, 'declined_count': 0, 'improvement_rate': 0},
                'monthly_summary': {'current_month': 'N/A', 'new_students': 0, 'assessments_completed': 0, 'alerts_generated': 0}
            }
        
        return render_template('dashboard/safe_index.html', 
            # Core metrics
            total_sections=total_sections,
            total_students=total_students,
            total_beneficiaries=total_beneficiaries,
            total_students_admin=total_students_admin,
            num_at_risk=num_at_risk,
            
            # Collections
            sections=sections,
            at_risk_students=at_risk_students[:10],  # Limit for performance
            
            # Analytics
            bmi_distribution=bmi_distribution,
            **dashboard_analytics,
            
            # Activity data
            recent_activities=recent_activities,
            recent_activity_count=recent_activity_count,
            today_logins=today_logins,
            today_failed_logins=today_failed_logins
        )
        
    except Exception as e:
        print(f"Admin dashboard error: {str(e)}")
        log_activity(current_user.id, 'dashboard_error', f'Admin dashboard error: {str(e)}', request.remote_addr)
        return _render_safe_admin_dashboard(recent_activities, recent_activity_count, today_logins, today_failed_logins)

def _get_school_admin_dashboard_data(school_id, recent_activities, recent_activity_count, today_logins, today_failed_logins, all_schools):
    """Get admin dashboard data for a specific school (used by super admin when viewing a school)"""
    try:
        selected_school = School.query.get(school_id)
        if not selected_school:
            flash('School not found', 'danger')
            return redirect(url_for('school.dashboard'))
        
        # Get sections and students for the selected school
        sections = Section.query.filter_by(school_id=school_id).all()
        school_students = Student.query.filter_by(school_id=school_id).all()
        
        # Calculate core metrics
        total_sections = len(sections) if sections else 0
        total_students = len(school_students) if school_students else 0
        total_students_admin = total_students  # For super admin view, all students count
        
        # Calculate BMI distribution
        bmi_distribution = _calculate_student_bmi_distribution(school_students)
        
        # Get beneficiary and at-risk students
        try:
            beneficiary_students = _get_beneficiary_students(school_students)
        except Exception as e:
            print(f"Error getting beneficiary students: {str(e)}")
            beneficiary_students = []
            
        try:
            at_risk_students = _get_at_risk_students(school_students)
        except Exception as e:
            print(f"Error getting at-risk students: {str(e)}")
            at_risk_students = []
        
        total_beneficiaries = len(beneficiary_students)
        num_at_risk = len(at_risk_students)
        
        # Calculate analytics
        try:
            dashboard_analytics = _calculate_dashboard_analytics(sections, school_students, beneficiary_students)
        except Exception as e:
            print(f"Error calculating dashboard analytics: {str(e)}")
            dashboard_analytics = {
                'bmi_progress': {'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], 'values': [18.5, 18.5, 18.5, 18.5, 18.5, 18.5]},
                'section_analytics': {'labels': [], 'total_students': [], 'beneficiaries': [], 'participation_rate': []},
                'nutritional_trends': {'labels': [], 'healthy': [], 'at_risk': []},
                'health_metrics': {'improved_count': 0, 'stable_count': 0, 'declined_count': 0, 'improvement_rate': 0},
                'monthly_summary': {'current_month': 'N/A', 'new_students': 0, 'assessments_completed': 0, 'alerts_generated': 0}
            }
        
        return render_template('dashboard/safe_index.html', 
            # Core metrics
            total_sections=total_sections,
            total_students=total_students,
            total_beneficiaries=total_beneficiaries,
            total_students_admin=total_students_admin,
            num_at_risk=num_at_risk,
            
            # Collections
            sections=sections,
            at_risk_students=at_risk_students[:10],  # Limit for performance
            
            # Analytics
            bmi_distribution=bmi_distribution,
            **dashboard_analytics,
            
            # Activity data
            recent_activities=recent_activities,
            recent_activity_count=recent_activity_count,
            today_logins=today_logins,
            today_failed_logins=today_failed_logins,
            
            # School filter data (for dropdown)
            all_schools=all_schools,
            selected_school=selected_school,
            selected_school_id=school_id,
            is_super_admin_view=True  # Flag to show dropdown
        )
        
    except Exception as e:
        print(f"School admin dashboard error: {str(e)}")
        print(f"Error traceback: {traceback.format_exc()}")
        # Return safe fallback
        try:
            all_schools = School.query.order_by(School.name).all()
        except:
            all_schools = []
        return _render_safe_admin_dashboard(recent_activities, recent_activity_count, today_logins, today_failed_logins)

def _get_student_dashboard_data():
    """Get dashboard data for student users"""
    try:
        student = Student.query.filter_by(user_id=current_user.id).first()
        recent_activities = UserActivity.query.filter_by(
            user_id=current_user.id
        ).order_by(UserActivity.created_at.desc()).limit(5).all()
        
        return render_template('dashboard/student_dashboard.html', 
            student=student, 
            recent_activities=recent_activities
        )
    except Exception as e:
        print(f"Student dashboard error: {str(e)}")
        raise e

def _calculate_school_performance():
    """Calculate real school performance metrics for the overview report"""
    try:
        school_performance = []
        schools = School.query.all()
        
        for school in schools:
            # Get students in this school (include zero-student schools)
            students = Student.query.filter_by(school_id=school.id).all()
            student_count = len(students)

            # Calculate school metrics (handle zero-student case)
            if student_count == 0:
                beneficiaries = 0
                at_risk = 0
                with_bmi_data = 0
                data_completeness = 0
                improvement_rate = 0
                performance_score = 0
            else:
                beneficiaries = len([s for s in students if s.is_beneficiary])
                at_risk = len([s for s in students if s.bmi and (s.bmi < 18.5 or s.bmi >= 25)])
                with_bmi_data = len([s for s in students if s.bmi])

                # Performance score based on beneficiary improvement and data completeness
                # Higher score = better nutritional status + better data quality
                data_completeness = (with_bmi_data / student_count * 100) if student_count > 0 else 0

                # Calculate improvement indicator (students with normal BMI out of at-risk)
                improved = len([s for s in students if s.bmi and 18.5 <= s.bmi < 25 and s.is_beneficiary])
                improvement_rate = (improved / beneficiaries * 100) if beneficiaries > 0 else 0

                # Performance score = average of data completeness and improvement rate
                performance_score = round((data_completeness + improvement_rate) / 2, 1)
            
            # finalize entry
            school_performance.append({
                'name': school.name,
                'students_count': student_count,
                'beneficiaries': beneficiaries,
                'at_risk': at_risk,
                'performance_score': performance_score,
                'data_completeness': round(data_completeness, 1) if isinstance(data_completeness, (int, float)) else 0,
                'improvement_rate': round(improvement_rate, 1) if isinstance(improvement_rate, (int, float)) else 0
            })

        # Sort by performance score descending
        school_performance.sort(key=lambda x: x['performance_score'], reverse=True)
        # Return all registered schools (include those with zero students)
        result = school_performance

        # Return actual data only - no demo data
        # If no data, return empty list for accurate reporting
        if not result:
            result = []
            print("No school performance data available - returning empty list")

        return result
    except Exception as e:
        print(f"Error calculating school performance: {e}")
        # Return empty list on error - no demo data
        return []

def _calculate_progress_trends(students_with_bmi):
    """Calculate real progress trends from actual student data"""
    try:
        # Template expects 'labels' and 'values' keys for chart data
        # Return empty structure if no data
        if not students_with_bmi:
            return {
                'labels': [],
                'values': [],
                'nutritional_improvement': 0,
                'program_compliance': 0,
                'data_quality': 0
            }
        
        # Nutritional improvement: percentage of students with healthy BMI
        healthy_bmi = len([s for s in students_with_bmi if 18.5 <= s.bmi < 25])
        nutritional_improvement = round((healthy_bmi / len(students_with_bmi) * 100), 1)
        
        # Program compliance: percentage of at-risk students enrolled as beneficiaries
        at_risk_students = [s for s in students_with_bmi if s.bmi < 18.5 or s.bmi >= 25]
        at_risk_in_program = len([s for s in at_risk_students if s.is_beneficiary])
        program_compliance = round((at_risk_in_program / len(at_risk_students) * 100), 1) if at_risk_students else 0
        
        # Data quality: percentage of all students with BMI data
        total_students = Student.query.count()
        data_quality = round((len(students_with_bmi) / total_students * 100), 1) if total_students > 0 else 0
        
        return {
            'labels': [],  # Empty for now - can be populated with time-based labels if needed
            'values': [],  # Empty for now - can be populated with trend values if needed
            'nutritional_improvement': nutritional_improvement,
            'program_compliance': program_compliance,
            'data_quality': data_quality
        }
    except Exception as e:
        print(f"Error calculating progress trends: {e}")
        return {
            'labels': [],
            'values': [],
            'nutritional_improvement': 0,
            'program_compliance': 0,
            'data_quality': 0
        }

def _calculate_monthly_progress_trends():
    """Calculate monthly progress trends for the past 12 months (January-December)"""
    try:
        import calendar as cal_module
        current_date = datetime.now()
        months_data = []
        months_labels = []
        
        # Get data for each month (January to December)
        for month_num in range(1, 13):
            # Get month name
            month_name = cal_module.month_name[month_num]
            months_labels.append(month_name[:3])  # Short name (Jan, Feb, etc.)
            
            # Get students created this month
            month_students = Student.query.filter(
                text(f"MONTH(created_at) = {month_num} OR MONTH(updated_at) = {month_num}")
            ).all()
            
            if not month_students:
                # Use current system-wide average if no data for this month
                all_students = Student.query.filter(Student.bmi != None).all()
                if all_students:
                    healthy = len([s for s in all_students if 18.5 <= s.bmi < 25])
                    nutritional = (healthy / len(all_students) * 100)
                else:
                    nutritional = 0
            else:
                # Calculate metrics for this month
                with_bmi = [s for s in month_students if s.bmi]
                if with_bmi:
                    healthy = len([s for s in with_bmi if 18.5 <= s.bmi < 25])
                    nutritional = (healthy / len(with_bmi) * 100)
                else:
                    # Get system average
                    all_students = Student.query.filter(Student.bmi != None).all()
                    if all_students:
                        healthy = len([s for s in all_students if 18.5 <= s.bmi < 25])
                        nutritional = (healthy / len(all_students) * 100)
                    else:
                        nutritional = 0
            
            months_data.append(round(nutritional, 1))
        
        return {
            'labels': months_labels,
            'values': months_data
        }
    except Exception as e:
        print(f"Error calculating monthly progress trends: {e}")
        # Return empty/zero data - no demo data
        return {
            'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            'values': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # Return zeros instead of demo data
        }

def _calculate_compliance_stats(total_schools):
    """Calculate real compliance and audit statistics"""
    try:
        schools = School.query.all()
        
        complete_docs = 0  # Schools with all required data
        partial_docs = 0   # Schools with some data
        missing_docs = 0   # Schools with no data
        
        for school in schools:
            students = Student.query.filter_by(school_id=school.id).all()
            
            if not students:
                missing_docs += 1
            else:
                # Check if school has complete documentation
                with_bmi = len([s for s in students if s.bmi])
                with_sections = len([s for s in students if s.section_id])
                
                completeness_ratio = (with_bmi + with_sections) / (len(students) * 2)
                
                if completeness_ratio >= 0.9:  # 90% or more complete
                    complete_docs += 1
                elif completeness_ratio >= 0.5:  # 50% or more complete
                    partial_docs += 1
                else:
                    missing_docs += 1
        
        return {
            'complete_docs': complete_docs,
            'partial_docs': partial_docs,
            'missing_docs': missing_docs,
            'total_schools': total_schools
        }
    except Exception as e:
        print(f"Error calculating compliance stats: {e}")
        return {'complete_docs': 0, 'partial_docs': 0, 'missing_docs': 0, 'total_schools': total_schools}

def _calculate_audit_alerts():
    """Generate real audit alerts based on system data"""
    try:
        alerts = []
        
        # Alert 1: Schools with no students
        # Fix: Use simpler query to find schools with no students
        from sqlalchemy import func
        try:
            empty_schools = db.session.query(School).outerjoin(Student, School.id == Student.school_id).group_by(School.id).having(func.count(Student.id) == 0).count()
        except:
            # Fallback: count all schools and subtract those with students
            total_schools = School.query.count()
            schools_with_students = db.session.query(func.count(func.distinct(Student.school_id))).scalar() or 0
            empty_schools = max(0, total_schools - schools_with_students)
        if empty_schools > 0:
            alerts.append({
                'type': 'warning',
                'message': f'{empty_schools} school(s) have no registered students'
            })
        
        # Alert 2: Students without BMI data
        students_no_bmi = Student.query.filter(Student.bmi == None).count()
        total_students = Student.query.count()
        if total_students > 0:
            no_bmi_ratio = (students_no_bmi / total_students * 100)
            if no_bmi_ratio > 20:  # More than 20% missing BMI data
                alerts.append({
                    'type': 'danger',
                    'message': f'{round(no_bmi_ratio, 1)}% of students missing BMI data'
                })
        
        # Alert 3: At-risk students not in program
        at_risk_students = db.session.query(Student).filter(
            text("bmi IS NOT NULL AND (bmi < 18.5 OR bmi >= 25)")
        ).count()
        at_risk_in_program = Student.query.filter(
            Student.is_beneficiary == True,
            text("(bmi < 18.5 OR bmi >= 25)")
        ).count()
        
        if at_risk_students > 0:
            enrollment_ratio = (at_risk_in_program / at_risk_students * 100)
            if enrollment_ratio < 80:  # Less than 80% enrolled
                alerts.append({
                    'type': 'warning',
                    'message': f'Only {round(enrollment_ratio, 1)}% of at-risk students are in beneficiary program'
                })
        
        return alerts
    except Exception as e:
        print(f"Error calculating audit alerts: {e}")
        return []

def _get_top_performing_schools():
    """Get top performing schools based on real metrics"""
    try:
        school_performance = _calculate_school_performance()
        top_schools = []
        
        for school in school_performance[:3]:  # Top 3
            top_schools.append({
                'name': school['name'],
                'improvement_rate': school['improvement_rate'],
                'performance_score': school['performance_score']
            })
        
        return top_schools
    except Exception as e:
        print(f"Error getting top performing schools: {e}")
        return []

def _get_super_admin_dashboard_data(recent_activities, recent_activity_count, today_logins, today_failed_logins, school_id=None):
    """Get dashboard data for super admin users"""
    try:
        print("Starting super admin dashboard data collection...")
        
        # Get all schools for dropdown
        all_schools = School.query.order_by(School.name).all()
        print(f"Found {len(all_schools)} schools for dropdown")
        selected_school = None
        if school_id:
            selected_school = School.query.get(school_id)
        
        # If a school is selected, show that school's admin dashboard instead
        if school_id and selected_school:
            return _get_school_admin_dashboard_data(
                school_id, 
                recent_activities, 
                recent_activity_count, 
                today_logins, 
                today_failed_logins,
                all_schools
            )
        
        # Build base query filters based on school selection
        student_filter = Student.query
        admin_filter = User.query.filter_by(role='admin')
        section_filter = Section.query
        
        # System-wide statistics (filtered if school selected)
        total_schools = School.query.count() if not school_id else 1
        total_admins = admin_filter.count()
        total_students = student_filter.count()
        total_sections = section_filter.count()
        
        print(f"Basic stats: schools={total_schools}, admins={total_admins}, students={total_students}, sections={total_sections}")
        
        # Calculate system-wide BMI distribution (filtered if school selected)
        bmi_distribution = {'underweight': 0, 'normal': 0, 'overweight': 0, 'obese': 0, 'severely_wasted': 0, 'wasted': 0}
        # Fix: Use proper SQLAlchemy syntax for 'is not None'
        students_with_bmi_query = student_filter.filter(Student.bmi != None)
        students_with_bmi = students_with_bmi_query.all()
        
        for student in students_with_bmi:
            if student.bmi < 16:
                bmi_distribution['severely_wasted'] += 1
            elif student.bmi < 18.5:
                bmi_distribution['wasted'] += 1
                # Note: 'wasted' (BMI 16-18.5) is a subset of underweight, but we use 'wasted' for consistency
                # Do not double-count as 'underweight' to maintain accurate totals
            elif student.bmi < 25:
                bmi_distribution['normal'] += 1
            elif student.bmi < 30:
                bmi_distribution['overweight'] += 1
            else:
                bmi_distribution['obese'] += 1
        
        print(f"BMI distribution calculated: {bmi_distribution}")
        
        # Do NOT use demo data - show actual data or zero
        # If no BMI data, keep zeros to show accurate "No Data" state
        bmi_total = sum(bmi_distribution.values())
        if bmi_total == 0:
            print(f"No BMI data available - showing zeros for accurate reporting")
            # Keep zeros instead of demo data for accuracy
        
        # Calculate system-wide analytics variables (filtered if school selected)
        total_beneficiaries_system = student_filter.filter_by(is_beneficiary=True).count()
        # Fix: Use raw SQL to avoid Pyright type checking issues
        from sqlalchemy import text
        at_risk_query = student_filter.filter(
            text("bmi IS NOT NULL AND (bmi < 18.5 OR bmi >= 25)")
        )
        at_risk_students_system = at_risk_query.count()
        
        # ===== REAL DATA: Comparative Progress Report =====
        # Get 12-month progress trend data
        monthly_progress = _calculate_monthly_progress_trends()
        
        # ===== REAL DATA: Consolidated Student Nutritional Status Report =====
        # Build nutritional_status from BMI distribution (already calculated above)
        nutritional_status = {
            'severely_wasted': bmi_distribution['severely_wasted'],
            'wasted': bmi_distribution['wasted'],
            'normal': bmi_distribution['normal'],
            'overweight': bmi_distribution['overweight'],
            'obese': bmi_distribution['obese']
        }
        
        # ===== REAL DATA: School Performance Overview =====
        school_performance = _calculate_school_performance()
        
        # ===== REAL DATA: Comparative Progress Report =====
        progress_trends = _calculate_progress_trends(students_with_bmi)
        
        # ===== REAL DATA: Compliance & Audit Report =====
        compliance_stats = _calculate_compliance_stats(total_schools)
        audit_alerts = _calculate_audit_alerts()
        
        # Legacy mock data (kept for backward compatibility, can be removed)
        compliance_rate_system = 85  # This will be superseded by compliance_stats
        improvement_rate_system = 12  # This will be superseded by progress_trends
        
        # Mock top performing schools (can be enhanced later)
        top_performing_schools = _get_top_performing_schools()

        print("All data prepared, rendering template...")
        
        return render_template('dashboard/index.html', 
            # Core system statistics
            total_schools=total_schools,
            total_admins=total_admins,
            total_students=total_students,
            total_sections=total_sections,
            
            # Activity data
            recent_activities=recent_activities,
            recent_activity_count=recent_activity_count,
            today_logins=today_logins,
            today_failed_logins=today_failed_logins,
            
            # BMI distribution
            bmi_distribution=bmi_distribution,
            
            # Analytics variables
            total_beneficiaries_system=total_beneficiaries_system,
            at_risk_students_system=at_risk_students_system,
            compliance_rate_system=compliance_rate_system,
            improvement_rate_system=improvement_rate_system,
            
            # Consolidated nutritional status
            nutritional_status=nutritional_status,
            
            # Monthly progress trends (for comparative progress report)
            monthly_progress=monthly_progress,
            
            # School performance
            school_performance=school_performance,
            
            # Progress trends
            progress_trends=progress_trends,
            
            # Top performing schools
            top_performing_schools=top_performing_schools,
            
            # Compliance stats
            compliance_stats=compliance_stats,
            
            # Audit alerts
            audit_alerts=audit_alerts,
            
            # School filter data
            all_schools=all_schools,
            selected_school=selected_school,
            selected_school_id=school_id
        )
        
    except Exception as e:
        print(f"Super admin dashboard error: {str(e)}")
        print(f"Error traceback: {traceback.format_exc()}")
        # Get schools even in error case so dropdown works
        try:
            all_schools = School.query.order_by(School.name).all()
        except:
            all_schools = []
        # Return minimal data to prevent crashes
        return render_template('dashboard/index.html', 
            total_schools=0,
            total_admins=0,
            total_students=0,
            total_sections=0,
            recent_activities=[],
            bmi_distribution={'underweight': 0, 'normal': 0, 'overweight': 0, 'obese': 0, 'severely_wasted': 0, 'wasted': 0},
            recent_activity_count=0,
            today_logins=0,
            today_failed_logins=0,
            total_beneficiaries_system=0,
            at_risk_students_system=0,
            compliance_rate_system=0,
            improvement_rate_system=0,
            nutritional_status={'severely_wasted': 0, 'wasted': 0, 'normal': 0, 'overweight': 0, 'obese': 0},
            monthly_progress={'labels': ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], 'values': [0,0,0,0,0,0,0,0,0,0,0,0]},
            school_performance=[],
            progress_trends={'labels': [], 'values': []},
            top_performing_schools=[],
            compliance_stats={'complete_docs': 0, 'partial_docs': 0, 'missing_docs': 0, 'total_schools': 0},
            audit_alerts=[],
            # School filter data (even in error case)
            all_schools=all_schools,
            selected_school=None,
            selected_school_id=None
        )

def _render_safe_admin_dashboard(recent_activities, recent_activity_count, today_logins, today_failed_logins):
    """Render a safe fallback dashboard when errors occur"""
    return render_template('dashboard/safe_index.html', 
        total_sections=0, total_students=0, sections=[], 
        bmi_distribution={'normal': 0, 'wasted': 0, 'severely_wasted': 0, 'overweight': 0},
        recent_activities=recent_activities, recent_activity_count=recent_activity_count,
        today_logins=today_logins, today_failed_logins=today_failed_logins,
        total_beneficiaries=0, total_students_admin=0, num_at_risk=0, at_risk_students=[],
        bmi_progress={'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], 'values': [18.5, 18.5, 18.5, 18.5, 18.5, 18.5]}, 
        feeding_participation={'labels': [], 'values': []},
        nutritional_trends={'labels': [], 'healthy': [], 'at_risk': []},
        section_analytics={'labels': [], 'total_students': [], 'beneficiaries': [], 'participation_rate': []},
        health_metrics={'improved_count': 0, 'stable_count': 0, 'declined_count': 0, 'improvement_rate': 0},
        monthly_summary={'current_month': 'N/A', 'new_students': 0, 'assessments_completed': 0, 'alerts_generated': 0}
    )

def _calculate_accurate_bmi_distribution(students):
    """Calculate accurate BMI distribution with proper categorization"""
    try:
        distribution = {'normal': 0, 'wasted': 0, 'severely_wasted': 0, 'overweight': 0, 'obese': 0}
        
        if not students:
            return distribution
            
        students_with_bmi = [s for s in students if s.bmi is not None and s.bmi > 0]
        
        for student in students_with_bmi:
            bmi = student.bmi
            if bmi < 16:
                distribution['severely_wasted'] += 1
            elif bmi < 18.5:
                distribution['wasted'] += 1
            elif bmi < 25:
                distribution['normal'] += 1
            elif bmi < 30:
                distribution['overweight'] += 1
            else:
                distribution['obese'] += 1
        
        return distribution
    except Exception as e:
        print(f"BMI distribution calculation error: {str(e)}")
        return {'normal': 0, 'wasted': 0, 'severely_wasted': 0, 'overweight': 0, 'obese': 0}

def _get_at_risk_students(school_students):
    """Get at-risk students (severely underweight or obese)"""
    try:
        if not school_students:
            return []
            
        at_risk = []
        for student in school_students:
            # Check if student has valid BMI data
            if student.bmi is not None and student.bmi > 0:
                # At-risk students are those who are severely underweight (BMI < 16) or obese (BMI >= 30)
                if student.bmi < 16 or student.bmi >= 30:
                    at_risk.append(student)
        
        # Sort by BMI (most critical first)
        at_risk.sort(key=lambda s: s.bmi if s.bmi else 0)
        return at_risk
    except Exception as e:
        print(f"At-risk students calculation error: {str(e)}")
        return []

def _calculate_dashboard_analytics(sections, school_students, beneficiary_students):
    """Calculate comprehensive dashboard analytics"""
    try:
        analytics = {}
        
        # BMI Progress Tracking (improved)
        analytics['bmi_progress'] = _calculate_improved_bmi_progress(school_students)
        
        # Section Analytics (consolidated from multiple charts)
        analytics['section_analytics'] = _calculate_section_analytics(sections, school_students)
        
        # Nutritional Trends (replaces redundant charts)
        analytics['nutritional_trends'] = _calculate_nutritional_trends(school_students)
        
        # Health Metrics Summary
        analytics['health_metrics'] = _calculate_health_metrics(beneficiary_students)
        
        # Monthly Summary
        analytics['monthly_summary'] = _calculate_monthly_summary(school_students)
        
        return analytics
    except Exception as e:
        print(f"Dashboard analytics calculation error: {str(e)}")
        return {
            'bmi_progress': {'labels': [], 'values': []},
            'section_analytics': {'labels': [], 'total_students': [], 'beneficiaries': [], 'participation_rate': []},
            'nutritional_trends': {'labels': [], 'healthy': [], 'at_risk': []},
            'health_metrics': {'improved_count': 0, 'stable_count': 0, 'declined_count': 0, 'improvement_rate': 0},
            'monthly_summary': {'current_month': 'N/A', 'new_students': 0, 'assessments_completed': 0, 'alerts_generated': 0}
        }

def _calculate_improved_bmi_progress(students):
    """Calculate improved BMI progress with real data"""
    try:
        current_date = datetime.now()
        months = []
        bmi_values = []
        
        for i in range(6):
            month_date = current_date - timedelta(days=30*i)
            month_name = calendar.month_abbr[month_date.month]
            months.insert(0, month_name)
            
            # Get students with valid BMI data from this month
            month_students = [s for s in students if s.bmi is not None and s.bmi > 0 and s.created_at and 
                            s.created_at.month == month_date.month and s.created_at.year == month_date.year]
            
            if month_students:
                avg_bmi = sum(s.bmi for s in month_students) / len(month_students)
                bmi_values.insert(0, round(avg_bmi, 1))
            else:
                # Use overall average if no data for specific month
                all_students_with_bmi = [s for s in students if s.bmi is not None and s.bmi > 0]
                if all_students_with_bmi:
                    avg_bmi = sum(s.bmi for s in all_students_with_bmi) / len(all_students_with_bmi)
                    bmi_values.insert(0, round(avg_bmi, 1))
                else:
                    bmi_values.insert(0, 18.5)  # Default healthy BMI
        
        # Ensure we return proper lists, not functions
        return {'labels': list(months), 'values': list(bmi_values)}
    except Exception as e:
        print(f"Improved BMI progress calculation error: {str(e)}")
        return {'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], 'values': [18.5, 18.5, 18.5, 18.5, 18.5, 18.5]}

def _calculate_section_analytics(sections, school_students):
    """Calculate comprehensive section analytics"""
    try:
        if not sections:
            return {'labels': [], 'total_students': [], 'beneficiaries': [], 'participation_rate': []}
        
        labels = []
        total_students = []
        beneficiaries = []
        participation_rates = []
        
        for section in sections:
            section_students = [s for s in school_students if s.section_id == section.id]
            # Beneficiaries are students marked as beneficiaries or those with unhealthy BMI
            section_beneficiaries = [s for s in section_students if s.bmi is not None and s.bmi > 0 and 
                                   (s.is_beneficiary or (s.bmi < 18.5 or s.bmi >= 25))]
            
            labels.append(section.name)
            total_students.append(len(section_students))
            beneficiaries.append(len(section_beneficiaries))
            
            # Calculate participation rate (students with complete health data)
            complete_data = len([s for s in section_students if s.bmi is not None and s.bmi > 0])
            participation_rate = (complete_data / len(section_students) * 100) if section_students else 0
            participation_rates.append(round(participation_rate, 1))
        
        return {
            'labels': list(labels),
            'total_students': list(total_students),
            'beneficiaries': list(beneficiaries),
            'participation_rate': list(participation_rates)
        }
    except Exception as e:
        print(f"Section analytics calculation error: {str(e)}")
        return {'labels': [], 'total_students': [], 'beneficiaries': [], 'participation_rate': []}

def _calculate_nutritional_trends(students):
    """Calculate nutritional trends over time"""
    try:
        current_date = datetime.now()
        months = []
        healthy_counts = []
        at_risk_counts = []
        
        for i in range(6):
            month_date = current_date - timedelta(days=30*i)
            month_name = calendar.month_abbr[month_date.month]
            months.insert(0, month_name)
            
            # Count healthy vs at-risk students for each month
            month_students = [s for s in students if s.bmi is not None and s.bmi > 0 and s.created_at and 
                            s.created_at.month == month_date.month and s.created_at.year == month_date.year]
            
            healthy = len([s for s in month_students if 18.5 <= s.bmi < 25])
            at_risk = len([s for s in month_students if s.bmi < 18.5 or s.bmi >= 25])
            
            healthy_counts.insert(0, healthy)
            at_risk_counts.insert(0, at_risk)
        
        return {
            'labels': list(months),
            'healthy': list(healthy_counts),
            'at_risk': list(at_risk_counts)
        }
    except Exception as e:
        print(f"Nutritional trends calculation error: {str(e)}")
        return {'labels': [], 'healthy': [], 'at_risk': []}

def _calculate_health_metrics(beneficiary_students):
    """Calculate health improvement metrics"""
    try:
        if not beneficiary_students:
            return {'improved_count': 0, 'stable_count': 0, 'declined_count': 0, 'improvement_rate': 0}
        
        # Calculate health metrics based on current BMI status
        total = len(beneficiary_students)
        # Improved: Students with healthy BMI (18.5-24.9)
        improved = len([s for s in beneficiary_students if s.bmi is not None and s.bmi > 0 and 18.5 <= s.bmi < 25])
        # Stable: Students with mild health concerns (16-18.4 or 25-29.9)
        stable = len([s for s in beneficiary_students if s.bmi is not None and s.bmi > 0 and (16 <= s.bmi < 18.5 or 25 <= s.bmi < 30)])
        # Declined: Students with severe health concerns (BMI < 16 or BMI >= 30)
        declined = len([s for s in beneficiary_students if s.bmi is not None and s.bmi > 0 and (s.bmi < 16 or s.bmi >= 30)])
        
        improvement_rate = (improved / total * 100) if total > 0 else 0
        
        return {
            'improved_count': improved,
            'stable_count': stable,
            'declined_count': declined,
            'improvement_rate': round(improvement_rate, 1)
        }
    except Exception as e:
        print(f"Health metrics calculation error: {str(e)}")
        return {'improved_count': 0, 'stable_count': 0, 'declined_count': 0, 'improvement_rate': 0}

def _calculate_monthly_summary(students):
    """Calculate monthly summary statistics"""
    try:
        current_date = datetime.now()
        current_month = current_date.strftime('%B %Y')
        month_start = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Students added this month
        new_students = len([s for s in students if s.created_at and s.created_at >= month_start])
        
        # Assessments completed (students with valid BMI data)
        assessments = len([s for s in students if s.bmi is not None and s.bmi > 0])
        
        # Health alerts (at-risk students with severe conditions)
        alerts = len([s for s in students if s.bmi is not None and s.bmi > 0 and (s.bmi < 16 or s.bmi >= 30)])
        
        return {
            'current_month': current_month,
            'new_students': new_students,
            'assessments_completed': assessments,
            'alerts_generated': alerts
        }
    except Exception as e:
        print(f"Monthly summary calculation error: {str(e)}")
        return {
            'current_month': datetime.now().strftime('%B %Y'),
            'new_students': 0,
            'assessments_completed': 0,
            'alerts_generated': 0
        }

# Legacy functions removed - replaced with improved analytics above

# --- STUDENT MANAGEMENT (FOR ADMINS) ---
@bp.route('/students')
@login_required
def students():
    log_activity(current_user.id, 'view_students', 'Accessed students page', request.remote_addr)
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    search_query = request.args.get('search_query', '').strip()
    query = Student.query.filter_by(school_id=current_user.school_id)
    if search_query:
        # Use LIKE for MySQL (case-insensitive by default with utf8mb4_ci collation)
        query = query.filter(Student.name.like(f'%{search_query}%'))
    students = query.all()
    return render_template('admin/students.html', students=students, search_query=search_query)

@bp.route('/students/create', methods=['GET', 'POST'])
@login_required
def create_student():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            birth_date_str = request.form.get('birth_date')
            gender = request.form.get('gender')
            height = request.form.get('height')
            weight = request.form.get('weight')
            section_id = request.form.get('section_id')
            preferences = request.form.get('preferences', '')
            
            # Get grade_level_id from form
            grade_level_id = request.form.get('grade_level_id')
            
            # Validate required fields
            if not all([name, email, password, birth_date_str, gender, height, weight, section_id, grade_level_id]):
                flash('All fields are required', 'danger')
                return redirect(url_for('school.create_student'))
            
            # Check if email already exists
            if User.query.filter_by(email=email).first():
                flash('Email already exists. Please use a different email address.', 'danger')
                return redirect(url_for('school.create_student'))
            
            # Add validation for birth_date_str before parsing
            if birth_date_str:
                birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            else:
                flash('Birth date is required', 'danger')
                return redirect(url_for('school.create_student'))
            
            # Validate and convert data types with proper error handling
            try:
                height_float = float(height) if height else 0.0
                weight_float = float(weight) if weight else 0.0
                section_id_int = int(section_id) if section_id else 0
                grade_level_id_int = int(grade_level_id) if grade_level_id else 0
            except (ValueError, TypeError):
                flash('Invalid data format for height, weight, section, or grade level.', 'danger')
                return redirect(url_for('school.create_student'))
            
            # Validate that the section belongs to the selected grade level
            section = Section.query.filter_by(id=section_id_int, school_id=current_user.school_id).first()
            if not section:
                flash('Invalid section selected.', 'danger')
                return redirect(url_for('school.create_student'))
            
            if section.grade_level_id != grade_level_id_int:
                flash('The selected section does not belong to the selected grade level.', 'danger')
                return redirect(url_for('school.create_student'))
            
            # Create user account for student
            user = User(name=name, email=email, role='student', school_id=current_user.school_id)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # Get the user ID
            
            # Create student with proper attribute assignment
            student = Student()
            student.name = name
            student.birth_date = birth_date
            student.gender = gender
            student.height = height_float
            student.weight = weight_float
            student.section_id = section_id_int
            student.school_id = current_user.school_id
            student.user_id = user.id
            student.registered_by = current_user.id
            student.preferences = preferences
            
            # Calculate BMI
            student.calculate_bmi()
            
            # Determine if student is a beneficiary based on BMI
            if student.bmi and (student.bmi < 18.5 or student.bmi >= 25):
                student.is_beneficiary = True
            
            db.session.add(student)
            db.session.commit()
            
            # Send notification to student
            from app.services.notification_service import NotificationService
            from app.services.email_service import EmailService
            
            NotificationService.notify_account_created(
                user_id=user.id,
                password=password,
                created_by_name=current_user.name
            )
            
            # Send welcome email to student
            try:
                school = School.query.get(current_user.school_id) if current_user.school_id else None
                EmailService.send_welcome_email_student(
                    student_email=user.email,
                    student_name=user.name,
                    password=password,
                    school_name=school.name if school else None,
                    created_by_name=current_user.name
                )
            except Exception as e:
                current_app.logger.error(f"Failed to send welcome email to student {user.email}: {str(e)}")
            
            log_activity(current_user.id, 'create_student', f'Created student {name}', request.remote_addr)
            flash('Student created successfully!', 'success')
            return redirect(url_for('school.students'))
            
        except ValueError as e:
            flash('Invalid data format. Please check your inputs.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating student: {str(e)}', 'danger')
    
    # Check if admin has a school assigned
    if not current_user.school_id:
        flash('You must be assigned to a school to create students. Please contact the administrator.', 'danger')
        return redirect(url_for('school.dashboard'))
    
    # Get grade levels and sections for the admin's school
    grade_levels = GradeLevel.query.filter_by(school_id=current_user.school_id).order_by(GradeLevel.name).all()
    sections = Section.query.filter_by(school_id=current_user.school_id).all()
    
    # Create a dictionary mapping grade_level_id to sections for easier JavaScript access
    # Use string keys for JSON compatibility
    sections_by_grade = {}
    for section in sections:
        grade_key = str(section.grade_level_id)
        if grade_key not in sections_by_grade:
            sections_by_grade[grade_key] = []
        sections_by_grade[grade_key].append({
            'id': section.id,
            'name': section.name
        })
    
    return render_template('admin/create_student.html', 
                         grade_levels=grade_levels, 
                         sections=sections,
                         sections_by_grade=sections_by_grade)

@bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first_or_404()
    
    if request.method == 'POST':
        try:
            # Update student attributes
            student.name = request.form.get('name')
            birth_date_str = request.form.get('birth_date')
            student.gender = request.form.get('gender')
            
            # Safely convert form data with default values
            height_value = request.form.get('height')
            weight_value = request.form.get('weight')
            section_id_value = request.form.get('section_id')
            
            # Convert with proper validation
            if height_value is not None and height_value != '':
                try:
                    student.height = float(height_value)
                except ValueError:
                    flash('Invalid height value.', 'danger')
                    return redirect(url_for('school.edit_student', student_id=student_id))
            
            if weight_value is not None and weight_value != '':
                try:
                    student.weight = float(weight_value)
                except ValueError:
                    flash('Invalid weight value.', 'danger')
                    return redirect(url_for('school.edit_student', student_id=student_id))
            
            if section_id_value is not None and section_id_value != '':
                try:
                    student.section_id = int(section_id_value)
                except ValueError:
                    flash('Invalid section value.', 'danger')
                    return redirect(url_for('school.edit_student', student_id=student_id))
            
            student.preferences = request.form.get('preferences', '')
            
            if birth_date_str:
                student.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            
            # Recalculate BMI
            student.calculate_bmi()
            
            # Update beneficiary status based on BMI
            if student.bmi and (student.bmi < 18.5 or student.bmi >= 25):
                student.is_beneficiary = True
            else:
                student.is_beneficiary = False
            
            db.session.commit()
            
            # Send email notification to super admins about data update
            try:
                from app.services.email_service import EmailService
                super_admins = User.query.filter_by(role='super_admin').all()
                school = School.query.get(current_user.school_id) if current_user.school_id else None
                
                update_details = f"Updated student '{student.name}' (ID: {student.id})"
                if student.height and student.weight:
                    update_details += f" - Height: {student.height}cm, Weight: {student.weight}kg, BMI: {student.bmi:.2f}"
                
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
            
            log_activity(current_user.id, 'edit_student', f'Updated student {student.name}', request.remote_addr)
            flash('Student updated successfully!', 'success')
            return redirect(url_for('school.students'))
            
        except ValueError as e:
            flash('Invalid data format. Please check your inputs.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating student: {str(e)}', 'danger')
    
    sections = Section.query.filter_by(school_id=current_user.school_id).all()
    return render_template('admin/edit_student.html', student=student, sections=sections)

@bp.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first_or_404()
    
    try:
        student_name = student.name
        db.session.delete(student)
        db.session.commit()
        
        log_activity(current_user.id, 'delete_student', f'Deleted student {student_name}', request.remote_addr)
        flash('Student deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting student: {str(e)}', 'danger')
    
    return redirect(url_for('school.students'))

@bp.route('/students/<int:student_id>')
@login_required
def student_detail(student_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first_or_404()
    return render_template('admin/student_detail.html', student=student)

def _calculate_student_bmi_distribution(students):
    """Calculate BMI distribution for all students with BMI data"""
    try:
        distribution = {'normal': 0, 'wasted': 0, 'severely_wasted': 0, 'overweight': 0}
        
        if not students:
            return distribution
            
        # Get all students with valid BMI data
        students_with_bmi = [s for s in students if s.bmi is not None and s.bmi > 0]
        
        for student in students_with_bmi:
            bmi = student.bmi
            if bmi < 16:
                distribution['severely_wasted'] += 1
            elif bmi < 18.5:
                distribution['wasted'] += 1
            elif bmi < 25:
                distribution['normal'] += 1
            else:
                distribution['overweight'] += 1
        
        return distribution
    except Exception as e:
        print(f"BMI distribution calculation error: {str(e)}")
        return {'normal': 0, 'wasted': 0, 'severely_wasted': 0, 'overweight': 0}

def _get_beneficiary_students(school_students):
    """Get students explicitly marked as beneficiaries
    
    Note: This counts ONLY students with is_beneficiary = True
    It does NOT auto-include students with unhealthy BMI
    """
    try:
        if not school_students:
            return []
        
        beneficiaries = []
        for student in school_students:
            # Count ONLY students explicitly marked as beneficiaries
            if student.is_beneficiary:
                beneficiaries.append(student)
        
        return beneficiaries
    except Exception as e:
        print(f"Beneficiary students calculation error: {str(e)}")
        return []
