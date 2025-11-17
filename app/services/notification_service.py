from app import db
from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.user import User
from app.models.student import Student
from app.models.school import School
from flask import url_for, current_app
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading

class NotificationService:
    
    @staticmethod
    def create_notification(recipient_id, title, message, notification_type, 
                          priority='medium', related_entity_type=None, 
                          related_entity_id=None, action_url=None, action_text=None,
                          send_email=True, expires_in_days=30):
        """
        Create a new notification for a user
        """
        try:
            # Validate recipient_id
            if not recipient_id:
                current_app.logger.warning("Cannot create notification: recipient_id is None")
                return None
            
            # Verify recipient exists
            recipient = User.query.get(recipient_id)
            if not recipient:
                current_app.logger.warning(f"Cannot create notification: recipient with ID {recipient_id} not found")
                return None
            
            # Set expiration date
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None
            
            notification = Notification(
                recipient_id=recipient_id,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                action_url=action_url,
                action_text=action_text,
                expires_at=expires_at
            )
            
            db.session.add(notification)
            db.session.commit()
            
            # Send email notification if requested
            if send_email:
                NotificationService._send_email_notification(notification)
            
            return notification
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating notification: {str(e)}")
            return None
    
    @staticmethod
    def notify_account_created(user_id, password=None, created_by_name=None):
        """Notify user about account creation"""
        user = User.query.get(user_id)
        if not user:
            return
        
        title = "Welcome to NutriKid!"
        if password:
            message = f"Your account has been created successfully by {created_by_name or 'an administrator'}.\n\n"
            message += f"Login Details:\nEmail: {user.email}\nPassword: {password}\n\n"
            message += "Please change your password after your first login for security."
        else:
            message = f"Your account has been created successfully by {created_by_name or 'an administrator'}."
        
        NotificationService.create_notification(
            recipient_id=user_id,
            title=title,
            message=message,
            notification_type=NotificationType.ACCOUNT_CREATED.value,
            priority='high',
            action_url=url_for('auth.login'),
            action_text="Login Now"
        )
    
    @staticmethod
    def notify_account_updated(user_id, updated_by_name=None, changes=None):
        """Notify user about account updates"""
        title = "Account Updated"
        message = f"Your account has been updated by {updated_by_name or 'an administrator'}."
        if changes:
            message += f"\n\nChanges made:\n{changes}"
        
        NotificationService.create_notification(
            recipient_id=user_id,
            title=title,
            message=message,
            notification_type=NotificationType.ACCOUNT_UPDATED.value,
            priority='medium'
        )
    
    @staticmethod
    def notify_password_changed(user_id, changed_by_name=None):
        """Notify user about password change"""
        title = "Password Changed"
        message = f"Your password has been changed by {changed_by_name or 'an administrator'}."
        message += "\n\nIf you did not request this change, please contact your administrator immediately."
        
        NotificationService.create_notification(
            recipient_id=user_id,
            title=title,
            message=message,
            notification_type=NotificationType.PASSWORD_CHANGED.value,
            priority='high'
        )
    
    @staticmethod
    def notify_student_added(student_id, added_by_name=None):
        """Notify relevant users about new student"""
        student = Student.query.get(student_id)
        if not student:
            return
        
        # Notify the student if they have a user account
        if student.user:
            title = "Welcome to NutriKid!"
            message = f"You have been enrolled as a student by {added_by_name or 'an administrator'}.\n\n"
            message += f"School: {student.school.name if student.school else 'N/A'}\n"
            message += f"Section: {student.section.name if student.section else 'N/A'}"
            
            NotificationService.create_notification(
                recipient_id=student.user.id,
                title=title,
                message=message,
                notification_type=NotificationType.STUDENT_ADDED.value,
                priority='medium',
                related_entity_type='student',
                related_entity_id=student_id
            )
        
        # Notify school admins
        if student.school:
            admins = User.query.filter_by(role='admin', school_id=student.school.id).all()
            for admin in admins:
                title = "New Student Added"
                message = f"A new student '{student.name}' has been added to your school by {added_by_name or 'an administrator'}.\n\n"
                message += f"Section: {student.section.name if student.section else 'N/A'}"
                
                NotificationService.create_notification(
                    recipient_id=admin.id,
                    title=title,
                    message=message,
                    notification_type=NotificationType.STUDENT_ADDED.value,
                    priority='low',
                    related_entity_type='student',
                    related_entity_id=student_id,
                    action_url=url_for('school.students'),
                    action_text="View Students"
                )
    
    @staticmethod
    def notify_student_updated(student_id, updated_by_name=None, changes=None):  
        """Notify relevant users about student updates"""
        student = Student.query.get(student_id)
        if not student:
            return
        
        # Notify the student if they have a user account
        if student.user:
            title = "Profile Updated"
            message = f"Your profile has been updated by {updated_by_name or 'an administrator'}."
            if changes:
                message += f"\n\nChanges made:\n{changes}"
            
            NotificationService.create_notification(
                recipient_id=student.user.id,
                title=title,
                message=message,
                notification_type=NotificationType.STUDENT_UPDATED.value,
                priority='medium',
                related_entity_type='student',
                related_entity_id=student_id
            )
    
    @staticmethod
    def detect_and_notify_student_changes(student, old_data, updated_by_name=None):
        """Detect changes in student data and send detailed notification"""
        if not student or not student.user:
            return
        
        changes = []
        important_changes = []
        
        # Check for name change
        if old_data.get('name') and old_data['name'] != student.name:
            changes.append(f"• Name: {old_data['name']} → {student.name}")
            important_changes.append('name')
        
        # Check for gender change
        if old_data.get('gender') and old_data['gender'] != student.gender:
            changes.append(f"• Gender: {old_data['gender']} → {student.gender}")
        
        # Check for birth date change
        if old_data.get('birth_date') and old_data['birth_date'] != student.birth_date:
            old_bd = old_data['birth_date'].strftime('%Y-%m-%d') if hasattr(old_data['birth_date'], 'strftime') else str(old_data['birth_date'])
            new_bd = student.birth_date.strftime('%Y-%m-%d') if student.birth_date else 'N/A'
            changes.append(f"• Birth Date: {old_bd} → {new_bd}")
        
        # Check for height change
        if old_data.get('height') is not None and old_data['height'] != student.height:
            changes.append(f"• Height: {old_data['height']} cm → {student.height} cm")
            important_changes.append('height')
        
        # Check for weight change
        if old_data.get('weight') is not None and old_data['weight'] != student.weight:
            changes.append(f"• Weight: {old_data['weight']} kg → {student.weight} kg")
            important_changes.append('weight')
        
        # Check for BMI change
        if old_data.get('bmi') is not None and abs((old_data['bmi'] or 0) - (student.bmi or 0)) > 0.1:
            old_bmi = f"{old_data['bmi']:.1f}" if old_data['bmi'] else 'N/A'
            new_bmi = f"{student.bmi:.1f}" if student.bmi else 'N/A'
            changes.append(f"• BMI: {old_bmi} → {new_bmi}")
            
            # Get BMI category change
            old_category = NotificationService._get_bmi_category(old_data.get('bmi'))
            new_category = student.bmi_category
            if old_category != new_category:
                changes.append(f"• BMI Category: {old_category} → {new_category}")
                important_changes.append('bmi')
        
        # Check for section change
        if old_data.get('section_id') and old_data['section_id'] != student.section_id:
            from app.models.section import Section
            old_section = Section.query.get(old_data['section_id'])
            new_section = student.section
            old_section_name = old_section.name if old_section else 'N/A'
            new_section_name = new_section.name if new_section else 'N/A'
            changes.append(f"• Section: {old_section_name} → {new_section_name}")
            important_changes.append('section')
        
        # Check for preferences/allergies change
        if old_data.get('preferences') != student.preferences:
            old_pref = old_data.get('preferences') or 'None'
            new_pref = student.preferences or 'None'
            changes.append(f"• Dietary Preferences/Allergies: {old_pref} → {new_pref}")
            important_changes.append('preferences')
        
        # Send notification if there are changes
        if changes:
            # Determine priority based on type of changes
            priority = 'high' if important_changes else 'medium'
            
            title = "Your Profile Has Been Updated"
            message = f"Your student profile was updated by {updated_by_name or 'an administrator'}.\n\n"
            message += "\n".join(changes)
            
            # Add health advice if BMI changed
            if 'bmi' in important_changes and student.bmi:
                message += "\n\n📊 Health Status Update:\n"
                if student.bmi < 18.5:
                    message += "Your BMI indicates you may be underweight. Please consult with your school health advisor."
                elif student.bmi < 25:
                    message += "Your BMI is in the healthy range. Keep up the good work!"
                elif student.bmi < 30:
                    message += "Your BMI indicates you may be overweight. Consider a balanced diet and regular exercise."
                else:
                    message += "Your BMI indicates obesity. Please consult with your school health advisor for guidance."
            
            NotificationService.create_notification(
                recipient_id=student.user.id,
                title=title,
                message=message,
                notification_type=NotificationType.STUDENT_UPDATED.value,
                priority=priority,
                related_entity_type='student',
                related_entity_id=student.id,
                action_url=url_for('student.profile'),
                action_text="View Profile"
            )
    
    @staticmethod
    def _get_bmi_category(bmi):
        """Get BMI category from BMI value"""
        if not bmi:
            return 'No Data'
        if bmi < 16:
            return 'Severely Underweight'
        elif bmi < 18.5:
            return 'Underweight'
        elif bmi < 25:
            return 'Normal Weight'
        elif bmi < 30:
            return 'Overweight'
        else:
            return 'Obese'
    
    @staticmethod
    def notify_student_deleted(user_id, student_name, deleted_by_name=None):
        """Notify user about student account deletion"""
        title = "Account Removed"
        message = f"Your student account '{student_name}' has been removed by {deleted_by_name or 'an administrator'}."
        message += "\n\nIf you have any questions, please contact your school administrator."
        
        NotificationService.create_notification(
            recipient_id=user_id,
            title=title,
            message=message,
            notification_type=NotificationType.STUDENT_DELETED.value,
            priority='high'
        )
    
    @staticmethod
    def notify_section_changes(section_id, action, performed_by_name=None):
        """Notify relevant users about section changes"""
        from app.models.section import Section
        
        if action == 'created':
            section = Section.query.get(section_id)
            if not section:
                return
            
            # Notify school admins (but not the one who performed the action)
            if section.school:
                from flask_login import current_user
                admins = User.query.filter_by(role='admin', school_id=section.school.id).all()
                for admin in admins:
                    # Skip notification if the admin is the one who performed the action
                    if hasattr(current_user, 'id') and admin.id == current_user.id:
                        continue
                        
                    title = "New Section Created"
                    message = f"A new section '{section.name}' has been created in grade '{section.grade_level_obj.name}' by {performed_by_name or 'an administrator'}."
                    
                    NotificationService.create_notification(
                        recipient_id=admin.id,
                        title=title,
                        message=message,
                        notification_type=NotificationType.SECTION_CREATED.value,
                        priority='low',
                        related_entity_type='section',
                        related_entity_id=section_id,
                        action_url=url_for('section.grade_sections', grade_id=section.grade_level_id),
                        action_text="View Sections"
                    )
        
        elif action == 'updated':
            section = Section.query.get(section_id)
            if not section:
                return
            
            # Notify students in the section
            students = Student.query.filter_by(section_id=section_id).all()
            for student in students:
                if student.user:
                    title = "Section Updated"
                    message = f"Your section '{section.name}' has been updated by {performed_by_name or 'an administrator'}."
                    
                    NotificationService.create_notification(
                        recipient_id=student.user.id,
                        title=title,
                        message=message,
                        notification_type=NotificationType.SECTION_UPDATED.value,
                        priority='low',
                        related_entity_type='section',
                        related_entity_id=section_id
                    )
        
        elif action == 'deleted':
            # For deleted sections, we need to pass the section name and student list
            # This should be called before deletion with additional parameters
            pass
    
    @staticmethod
    def notify_grade_changes(grade_id, action, performed_by_name=None):
        """Notify relevant users about grade level changes"""
        from app.models.grade_level import GradeLevel
        
        if action in ['created', 'updated']:
            grade = GradeLevel.query.get(grade_id)
            if not grade:
                return
            
            # Notify school admins (but not the one who performed the action)
            if grade.school:
                from flask_login import current_user
                admins = User.query.filter_by(role='admin', school_id=grade.school.id).all()
                for admin in admins:
                    # Skip notification if the admin is the one who performed the action
                    if hasattr(current_user, 'id') and admin.id == current_user.id:
                        continue
                        
                    title = f"Grade Level {action.title()}"
                    message = f"Grade level '{grade.name}' has been {action} by {performed_by_name or 'an administrator'}."
                    
                    NotificationService.create_notification(
                        recipient_id=admin.id,
                        title=title,
                        message=message,
                        notification_type=getattr(NotificationType, f'GRADE_{action.upper()}').value,
                        priority='low',
                        related_entity_type='grade',
                        related_entity_id=grade_id,
                        action_url=url_for('section.index'),
                        action_text="View Grades"
                    )
    
    @staticmethod
    def notify_admin_assignment(user_id, school_name, assigned_by_name=None):
        """Notify user about admin role assignment"""
        title = "Administrator Role Assigned"
        message = f"You have been assigned as an administrator for '{school_name}' by {assigned_by_name or 'a super administrator'}."
        message += "\n\nYou now have access to manage students, sections, and generate reports for your school."
        
        NotificationService.create_notification(
            recipient_id=user_id,
            title=title,
            message=message,
            notification_type=NotificationType.ADMIN_ASSIGNED.value,
            priority='high',
            action_url=url_for('school.students'),
            action_text="Access Dashboard"
        )
    
    @staticmethod
    def notify_school_updated(school_id, updated_by_name=None, changes=None):
        """Notify all admins of a school when school information is updated by super admin"""
        school = School.query.get(school_id)
        if not school:
            return
        
        # Get all admins for this school
        admins = User.query.filter_by(role='admin', school_id=school_id).all()
        
        if not admins:
            return
        
        title = "School Information Updated"
        message = f"Your school '{school.name}' information has been updated by {updated_by_name or 'a super administrator'}."
        
        if changes:
            message += f"\n\nChanges made:\n{changes}"
        else:
            message += "\n\nPlease review the updated school details in your dashboard."
        
        # Notify all admins of the school
        for admin in admins:
            NotificationService.create_notification(
                recipient_id=admin.id,
                title=title,
                message=message,
                notification_type=NotificationType.SCHOOL_UPDATED.value,
                priority='medium',
                related_entity_type='school',
                related_entity_id=school_id,
                action_url=url_for('school.dashboard'),
                action_text="View Dashboard"
            )
    
    @staticmethod
    def notify_school_deleted(school_name, admin_ids, deleted_by_name=None):
        """Notify admins when their school is deleted"""
        title = "School Removed"
        message = f"Your school '{school_name}' has been removed from the system by {deleted_by_name or 'a super administrator'}."
        message += "\n\nIf you have any questions, please contact the super administrator."
        
        for admin_id in admin_ids:
            NotificationService.create_notification(
                recipient_id=admin_id,
                title=title,
                message=message,
                notification_type=NotificationType.SCHOOL_UPDATED.value,
                priority='high'
            )
    
    @staticmethod
    def notify_admin_student_operation(school_id, operation, student_name, performed_by_name=None, details=None):
        """Notify all admins of a school about student operations (create, update, delete)"""
        if not school_id:
            return
        
        school = School.query.get(school_id)
        if not school:
            return
        
        # Get all admins for this school
        admins = User.query.filter_by(role='admin', school_id=school_id).all()
        
        if not admins:
            return
        
        # Determine notification details based on operation
        if operation == 'created':
            title = "New Student Added"
            message = f"A new student '{student_name}' has been added to your school by {performed_by_name or 'a super administrator'}."
            notification_type = NotificationType.STUDENT_ADDED.value
            priority = 'medium'
            action_url = url_for('school.students')
            action_text = "View Students"
        elif operation == 'updated':
            title = "Student Information Updated"
            message = f"Student '{student_name}' information has been updated by {performed_by_name or 'a super administrator'}."
            if details:
                message += f"\n\nChanges made:\n{details}"
            notification_type = NotificationType.STUDENT_UPDATED.value
            priority = 'medium'
            action_url = url_for('school.students')
            action_text = "View Students"
        elif operation == 'deleted':
            title = "Student Removed"
            message = f"Student '{student_name}' has been removed from your school by {performed_by_name or 'a super administrator'}."
            notification_type = NotificationType.STUDENT_DELETED.value
            priority = 'high'
            action_url = url_for('school.students')
            action_text = "View Students"
        else:
            return
        
        # Notify all admins of the school
        for admin in admins:
            NotificationService.create_notification(
                recipient_id=admin.id,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                related_entity_type='student',
                related_entity_id=None,
                action_url=action_url,
                action_text=action_text
            )
    
    @staticmethod
    def notify_admin_admin_removed(school_id, removed_admin_name, removed_by_name=None):
        """Notify other admins in the same school when an admin is removed"""
        if not school_id:
            return
        
        # Get all remaining admins for this school
        admins = User.query.filter_by(role='admin', school_id=school_id).all()
        
        if not admins:
            return
        
        title = "Administrator Removed"
        message = f"Administrator '{removed_admin_name}' has been removed from your school by {removed_by_name or 'a super administrator'}."
        
        # Notify all remaining admins
        for admin in admins:
            NotificationService.create_notification(
                recipient_id=admin.id,
                title=title,
                message=message,
                notification_type=NotificationType.ADMIN_REMOVED.value,
                priority='high',
                related_entity_type='admin',
                related_entity_id=None,
                action_url=url_for('school.dashboard'),
                action_text="View Dashboard"
            )
    
    @staticmethod
    def _send_email_notification(notification):
        """Send email notification (runs in background thread)"""
        def send_email():
            try:
                user = User.query.get(notification.recipient_id)
                if not user or not user.email:
                    return
                
                # Email configuration (you should move these to environment variables)
                smtp_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
                smtp_port = current_app.config.get('MAIL_PORT', 587)
                smtp_username = current_app.config.get('MAIL_USERNAME')
                smtp_password = current_app.config.get('MAIL_PASSWORD')
                
                if not smtp_username or not smtp_password:
                    current_app.logger.warning("Email credentials not configured")
                    return
                
                # Create email
                msg = MIMEMultipart()
                msg['From'] = smtp_username
                msg['To'] = user.email
                msg['Subject'] = f"NutriKid - {notification.title}"
                
                # Email body
                body = f"""
Dear {user.name},

{notification.message}

---
This is an automated notification from NutriKid School Nutrition Management System.
If you have any questions, please contact your administrator.

Best regards,
NutriKid Team
                """
                
                msg.attach(MIMEText(body, 'plain'))
                
                # Send email
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(smtp_username, smtp_password)
                text = msg.as_string()
                server.sendmail(smtp_username, user.email, text)
                server.quit()
                
                # Update notification status
                notification.is_email_sent = True
                notification.email_sent_at = datetime.utcnow()
                db.session.commit()
                
            except Exception as e:
                current_app.logger.error(f"Error sending email notification: {str(e)}")
        
        # Run email sending in background thread
        thread = threading.Thread(target=send_email)
        thread.daemon = True
        thread.start()
    
    @staticmethod
    def mark_notification_as_read(notification_id, user_id):
        """Mark a notification as read"""
        notification = Notification.query.filter_by(id=notification_id, recipient_id=user_id).first()
        if notification:
            notification.mark_as_read()
            return True
        return False
    
    @staticmethod
    def mark_all_as_read(user_id):
        """Mark all notifications as read for a user"""
        notifications = Notification.query.filter_by(recipient_id=user_id, is_read=False).all()
        for notification in notifications:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
        db.session.commit()
        return len(notifications)
    
    @staticmethod
    def cleanup_old_notifications(days=90):
        """Clean up old notifications"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        old_notifications = Notification.query.filter(
            Notification.created_at < cutoff_date
        ).all()
        
        for notification in old_notifications:
            db.session.delete(notification)
        
        db.session.commit()
        return len(old_notifications)