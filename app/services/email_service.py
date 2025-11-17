from flask import current_app
from flask_mail import Message
import logging

# Import mail instance from app
try:
    from app import mail
    MAIL_AVAILABLE = True
except ImportError:
    mail = None
    MAIL_AVAILABLE = False

class EmailService:
    """Service for handling email notifications"""

    @staticmethod
    def send_email(
        to=None,
        subject=None,
        body=None,
        html_body=None,
        *,
        recipients=None,
        text_body=None,
    ):
        """
        Send an email notification.

        Compatibility:
        - Supports both legacy signature (to, subject, body, html_body)
          and new keyword style (subject=..., recipients=[...], text_body=..., html_body=...).

        Returns True on success, False on failure.
        """
        try:
            # Check if mail service is available
            if not MAIL_AVAILABLE or mail is None:
                # Fallback to logging if mail is not available
                current_app.logger.info("EMAIL SERVICE NOT AVAILABLE - FALLING BACK TO LOGGING")
                return EmailService._log_email(to, subject, body, html_body, recipients, text_body)
            
            # Normalize inputs
            recipient_list = []
            if recipients and isinstance(recipients, (list, tuple)):
                recipient_list = list(recipients)
            elif to:
                recipient_list = [to]
            
            if not recipient_list:
                current_app.logger.error("No recipients specified for email")
                return False
            
            text = text_body if text_body is not None else body
            
            # Log email details for debugging
            current_app.logger.info(f"Preparing to send email to: {', '.join(recipient_list)}")
            current_app.logger.info(f"Subject: {subject}")
            
            # Create message
            msg = Message(
                subject=subject,
                recipients=recipient_list,
                body=text,
                html=html_body
            )
            
            # Send email
            mail.send(msg)
            current_app.logger.info(f"Email sent successfully to {', '.join(recipient_list)}")
            return True
            
        except Exception as e:
            # Try to include a best-effort recipient for error context
            safe_to = to if to else (recipients[0] if isinstance(recipients, (list, tuple)) and recipients else 'unknown')
            current_app.logger.error(f"Failed to send email to {safe_to}: {str(e)}")
            return False
    
    @staticmethod
    def _log_email(to=None, subject=None, body=None, html_body=None, recipients=None, text_body=None):
        """Fallback method to log emails when mail service is not available"""
        try:
            # Normalize inputs
            recipient_list = []
            if recipients and isinstance(recipients, (list, tuple)):
                recipient_list = list(recipients)
            elif to:
                recipient_list = [to]

            text = text_body if text_body is not None else body

            # Log the email
            current_app.logger.info("EMAIL NOTIFICATION:")
            current_app.logger.info(f"To: {', '.join(recipient_list) if recipient_list else 'N/A'}")
            current_app.logger.info(f"Subject: {subject}")
            current_app.logger.info(f"Body: {text}")
            if html_body:
                current_app.logger.info("HTML Body present")

            return True

        except Exception as e:
            # Try to include a best-effort recipient for error context
            safe_to = to if to else (recipients[0] if isinstance(recipients, (list, tuple)) and recipients else 'unknown')
            current_app.logger.error(f"Failed to log email to {safe_to}: {str(e)}")
            return False
    
    @staticmethod
    def send_password_reset_notification(user_email, user_name, reset_token=None):
        """
        Send password reset notification email
        
        Args:
            user_email (str): User's email address
            user_name (str): User's name
            reset_token (str, optional): Password reset token
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Password Reset Request - NutriKid"
        
        if reset_token:
            # Direct password reset email (if implementing direct reset)
            body = f"""
Hello {user_name},

You have requested a password reset for your NutriKid account.

If you did not request this reset, please ignore this email.

Best regards,
NutriKid Team
            """
        else:
            # Admin approval required email
            body = f"""
Hello {user_name},

Your password reset request has been submitted and is pending approval from your administrator.

You will receive another notification once your request has been processed.

Best regards,
NutriKid Team
            """
        
        return EmailService.send_email(user_email, subject, body)
    
    @staticmethod
    def send_admin_notification(admin_email, admin_name, user_name, user_role):
        """
        Send notification to admin about password reset request
        
        Args:
            admin_email (str): Admin's email address
            admin_name (str): Admin's name
            user_name (str): User requesting reset
            user_role (str): Role of user requesting reset
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = f"Password Reset Request - {user_name} ({user_role})"
        
        body = f"""
Hello {admin_name},

A password reset request has been submitted by:
- Name: {user_name}
- Role: {user_role.title()}

Please log in to the NutriKid system to review and process this request.

Best regards,
NutriKid System
        """
        
        return EmailService.send_email(admin_email, subject, body)
    
    @staticmethod
    def send_password_reset_approved(user_email, user_name, new_password):
        """
        Send notification when password reset is approved with new password
        
        Args:
            user_email (str): User's email address
            user_name (str): User's name
            new_password (str): New temporary password
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Password Reset Approved - NutriKid"
        
        body = f"""
Hello {user_name},

Your password reset request has been approved.

Your new temporary password is: {new_password}

Please log in with this password and change it immediately for security.

Best regards,
NutriKid Team
        """
        
        return EmailService.send_email(user_email, subject, body)
    
    @staticmethod
    def send_password_reset_denied(user_email, user_name, reason=None):
        """
        Send notification when password reset is denied
        
        Args:
            user_email (str): User's email address
            user_name (str): User's name
            reason (str, optional): Reason for denial
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Password Reset Request Denied - NutriKid"
        
        body = f"""
Hello {user_name},

Your password reset request has been denied.

{f"Reason: {reason}" if reason else ""}

Please contact your administrator if you need further assistance.

Best regards,
NutriKid Team
        """
        
        return EmailService.send_email(user_email, subject, body)
    
    @staticmethod
    def send_welcome_email_admin(admin_email, admin_name, password, school_name=None, created_by_name=None):
        """
        Send welcome email to newly created admin account
        
        Args:
            admin_email (str): Admin's email address
            admin_name (str): Admin's name
            password (str): Temporary password
            school_name (str, optional): School name if assigned
            created_by_name (str, optional): Name of person who created the account
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Welcome to NutriKid - Your Admin Account Has Been Created"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .credentials {{ background: #fff; padding: 20px; border-left: 4px solid #667eea; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to NutriKid!</h1>
                </div>
                <div class="content">
                    <p>Hello <strong>{admin_name}</strong>,</p>
                    
                    <p>Your admin account has been successfully created{f' by {created_by_name}' if created_by_name else ''}.</p>
                    
                    {f'<p>You have been assigned to: <strong>{school_name}</strong></p>' if school_name else ''}
                    
                    <p>You can now log in to the NutriKid School Nutrition Management System using the following credentials:</p>
                    
                    <div class="credentials">
                        <p><strong>Email:</strong> {admin_email}</p>
                        <p><strong>Temporary Password:</strong> {password}</p>
                    </div>
                    
                    <p><strong>Important:</strong> Please change your password immediately after your first login for security purposes.</p>
                    
                    <p>As an admin, you can:</p>
                    <ul>
                        <li>Manage student records and nutritional data</li>
                        <li>Generate and submit nutritional reports</li>
                        <li>Monitor student health status</li>
                        <li>Manage beneficiary lists</li>
                    </ul>
                    
                    <p>If you have any questions or need assistance, please contact your system administrator.</p>
                    
                    <p>Best regards,<br>
                    <strong>NutriKid Team</strong></p>
                </div>
                <div class="footer">
                    <p>This is an automated email. Please do not reply to this message.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
Hello {admin_name},

Your admin account has been successfully created{f' by {created_by_name}' if created_by_name else ''}.

{f'You have been assigned to: {school_name}' if school_name else ''}

You can now log in to the NutriKid School Nutrition Management System using the following credentials:

Email: {admin_email}
Temporary Password: {password}

IMPORTANT: Please change your password immediately after your first login for security purposes.

As an admin, you can:
- Manage student records and nutritional data
- Generate and submit nutritional reports
- Monitor student health status
- Manage beneficiary lists

If you have any questions or need assistance, please contact your system administrator.

Best regards,
NutriKid Team
        """
        
        return EmailService.send_email(
            to=admin_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_welcome_email_student(student_email, student_name, password, school_name=None, created_by_name=None):
        """
        Send welcome email to newly created student account
        
        Args:
            student_email (str): Student's email address
            student_name (str): Student's name
            password (str): Temporary password
            school_name (str, optional): School name
            created_by_name (str, optional): Name of person who created the account
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Welcome to NutriKid - Your Student Account Has Been Created"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .credentials {{ background: #fff; padding: 20px; border-left: 4px solid #28a745; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to NutriKid!</h1>
                </div>
                <div class="content">
                    <p>Hello <strong>{student_name}</strong>,</p>
                    
                    <p>Your student account has been successfully created{f' by {created_by_name}' if created_by_name else ''}.</p>
                    
                    {f'<p>You are enrolled at: <strong>{school_name}</strong></p>' if school_name else ''}
                    
                    <p>You can now log in to the NutriKid School Nutrition Management System using the following credentials:</p>
                    
                    <div class="credentials">
                        <p><strong>Email:</strong> {student_email}</p>
                        <p><strong>Temporary Password:</strong> {password}</p>
                    </div>
                    
                    <p><strong>Important:</strong> Please change your password immediately after your first login for security purposes.</p>
                    
                    <p>As a student, you can:</p>
                    <ul>
                        <li>View your nutritional records and BMI status</li>
                        <li>Track your health progress</li>
                        <li>View your profile information</li>
                        <li>Access your dashboard</li>
                    </ul>
                    
                    <p>If you have any questions or need assistance, please contact your school administrator.</p>
                    
                    <p>Best regards,<br>
                    <strong>NutriKid Team</strong></p>
                </div>
                <div class="footer">
                    <p>This is an automated email. Please do not reply to this message.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
Hello {student_name},

Your student account has been successfully created{f' by {created_by_name}' if created_by_name else ''}.

{f'You are enrolled at: {school_name}' if school_name else ''}

You can now log in to the NutriKid School Nutrition Management System using the following credentials:

Email: {student_email}
Temporary Password: {password}

IMPORTANT: Please change your password immediately after your first login for security purposes.

As a student, you can:
- View your nutritional records and BMI status
- Track your health progress
- View your profile information
- Access your dashboard

If you have any questions or need assistance, please contact your school administrator.

Best regards,
NutriKid Team
        """
        
        return EmailService.send_email(
            to=student_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_report_notification_to_super_admin(super_admin_email, super_admin_name, admin_name, school_name, student_count):
        """
        Send email notification to super admin when admin submits a report
        
        Args:
            super_admin_email (str): Super admin's email address
            super_admin_name (str): Super admin's name
            admin_name (str): Admin who submitted the report
            school_name (str): School name
            student_count (int): Number of students in the report
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = f"New Nutritional Report Submitted - {school_name}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #dc3545 0%, #c82333 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .info-box {{ background: #fff; padding: 20px; border-left: 4px solid #dc3545; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #dc3545; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>New Report Submitted</h1>
                </div>
                <div class="content">
                    <p>Hello <strong>{super_admin_name}</strong>,</p>
                    
                    <p>A new student nutritional report has been submitted and requires your review.</p>
                    
                    <div class="info-box">
                        <p><strong>Admin:</strong> {admin_name}</p>
                        <p><strong>School:</strong> {school_name}</p>
                        <p><strong>Number of Students:</strong> {student_count}</p>
                    </div>
                    
                    <p>Please log in to the NutriKid system to review the report details.</p>
                    
                    <p>Best regards,<br>
                    <strong>NutriKid System</strong></p>
                </div>
                <div class="footer">
                    <p>This is an automated notification. Please do not reply to this message.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
Hello {super_admin_name},

A new student nutritional report has been submitted and requires your review.

Admin: {admin_name}
School: {school_name}
Number of Students: {student_count}

Please log in to the NutriKid system to review the report details.

Best regards,
NutriKid System
        """
        
        return EmailService.send_email(
            to=super_admin_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_admin_update_notification_to_super_admin(super_admin_email, super_admin_name, admin_name, school_name, update_type, update_details):
        """
        Send email notification to super admin when admin updates data
        
        Args:
            super_admin_email (str): Super admin's email address
            super_admin_name (str): Super admin's name
            admin_name (str): Admin who made the update
            school_name (str): School name
            update_type (str): Type of update (e.g., 'student_created', 'student_updated', 'data_modified')
            update_details (str): Details about the update
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = f"Data Update Notification - {school_name}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #ffc107 0%, #ff9800 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .info-box {{ background: #fff; padding: 20px; border-left: 4px solid #ffc107; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Data Update Notification</h1>
                </div>
                <div class="content">
                    <p>Hello <strong>{super_admin_name}</strong>,</p>
                    
                    <p>An admin has made updates to the system data.</p>
                    
                    <div class="info-box">
                        <p><strong>Admin:</strong> {admin_name}</p>
                        <p><strong>School:</strong> {school_name}</p>
                        <p><strong>Update Type:</strong> {update_type.replace('_', ' ').title()}</p>
                        <p><strong>Details:</strong> {update_details}</p>
                    </div>
                    
                    <p>Please log in to the NutriKid system to review the changes.</p>
                    
                    <p>Best regards,<br>
                    <strong>NutriKid System</strong></p>
                </div>
                <div class="footer">
                    <p>This is an automated notification. Please do not reply to this message.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
Hello {super_admin_name},

An admin has made updates to the system data.

Admin: {admin_name}
School: {school_name}
Update Type: {update_type.replace('_', ' ').title()}
Details: {update_details}

Please log in to the NutriKid system to review the changes.

Best regards,
NutriKid System
        """
        
        return EmailService.send_email(
            to=super_admin_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body
        )