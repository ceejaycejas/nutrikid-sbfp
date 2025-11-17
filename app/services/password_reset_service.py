from flask import current_app, url_for
from app import db
from app.models.user import User
from app.models.password_reset import PasswordResetRequest
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType
from datetime import datetime, timedelta
import secrets
import string
from typing import List, Tuple, Optional


class PasswordResetService:
    """Service for handling password reset requests and workflow"""
    
    @staticmethod
    def create_reset_request(user_id: int, reason: Optional[str] = None) -> Tuple[Optional[PasswordResetRequest], str]:
        """Create a new password reset request"""
        try:
            user = User.query.get(user_id)
            if not user:
                return None, "User not found"
            
            # Check if user already has a pending request
            existing_request = PasswordResetRequest.query.filter_by(
                user_id=user_id, 
                status='pending'
            ).first()
            
            if existing_request and not existing_request.is_expired():
                return None, "You already have a pending password reset request"
            
            # Create new request
            reset_request = PasswordResetRequest(user_id=user_id, reason=reason)
            db.session.add(reset_request)
            db.session.commit()
            
            # Send notifications based on user role
            if user.role == 'admin':
                PasswordResetService._notify_super_admin_of_admin_request(reset_request)
            
            return reset_request, "Password reset request submitted successfully"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating password reset request: {str(e)}")
            return None, "An error occurred while processing your request"
    
    @staticmethod
    def _notify_super_admin_of_admin_request(reset_request: PasswordResetRequest) -> None:
        """Notify super admin when admin requests password reset"""
        admin = reset_request.user
        
        # Get super admins
        super_admins = User.query.filter_by(role='super_admin').all()
        
        for super_admin in super_admins:
            # Create notification
            title = "Admin Password Reset Request"
            message = f"Administrator {admin.name} ({admin.email}) has requested a password reset."
            if reset_request.reason:
                message += f"\n\nReason: {reset_request.reason}"
            message += f"\n\nPlease review and approve/reject this request."
            
            NotificationService.create_notification(
                recipient_id=super_admin.id,
                title=title,
                message=message,
                notification_type=NotificationType.SECURITY_ALERT.value,
                priority='high',
                related_entity_type='password_reset',
                related_entity_id=reset_request.id,
                action_url=None,
                action_text=None,
                send_email=True
            )
    
    @staticmethod
    def approve_request(request_id: int, approved_by_id: int, admin_notes: Optional[str] = None) -> Tuple[bool, str]:
        """Approve a password reset request"""
        try:
            reset_request = PasswordResetRequest.query.get(request_id)
            if not reset_request:
                return False, "Request not found"
            
            if not reset_request.can_be_approved():
                return False, "Request cannot be approved (expired or already processed)"
            
            # Approve the request
            success = reset_request.approve(approved_by_id, admin_notes)
            if not success:
                return False, "Failed to approve request"
            
            # Generate temporary password
            temp_password = PasswordResetService._generate_temp_password()
            
            # Update user password
            user = reset_request.user
            user.set_password(temp_password)
            db.session.commit()
            
            # Mark request as completed
            reset_request.complete()
            
            # Send new password to user
            PasswordResetService._send_new_password_email(user, temp_password, reset_request)
            
            # Notify user via system notification
            NotificationService.create_notification(
                recipient_id=user.id,
                title="Password Reset Approved",
                message="Your password reset request has been approved. A new temporary password has been sent to your email address. Please log in and change your password immediately.",
                notification_type=NotificationType.PASSWORD_CHANGED.value,
                priority='high',
                action_url=url_for('auth.login'),
                action_text="Login Now",
                send_email=False  # Don't send email notification since we're sending the password separately
            )
            
            return True, "Request approved and new password sent to user"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error approving password reset request: {str(e)}")
            return False, "An error occurred while processing the request"
    
    @staticmethod
    def reject_request(request_id: int, approved_by_id: int, admin_notes: Optional[str] = None) -> Tuple[bool, str]:
        """Reject a password reset request"""
        try:
            reset_request = PasswordResetRequest.query.get(request_id)
            if not reset_request:
                return False, "Request not found"
            
            if reset_request.status != 'pending':
                return False, "Request has already been processed"
            
            # Reject the request
            success = reset_request.reject(approved_by_id, admin_notes)
            if not success:
                return False, "Failed to reject request"
            
            # Notify user
            user = reset_request.user
            message = "Your password reset request has been rejected."
            if admin_notes:
                message += f"\n\nReason: {admin_notes}"
            message += "\n\nIf you believe this is an error, please contact your administrator."
            
            NotificationService.create_notification(
                recipient_id=user.id,
                title="Password Reset Request Rejected",
                message=message,
                notification_type=NotificationType.SECURITY_ALERT.value,
                priority='medium',
                send_email=True
            )
            
            return True, "Request rejected and user notified"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error rejecting password reset request: {str(e)}")
            return False, "An error occurred while processing the request"
    
    @staticmethod
    def _generate_temp_password() -> str:
        """Generate a secure temporary password"""
        # Generate a password with uppercase, lowercase, numbers, and special chars
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(chars) for _ in range(12))
    
    @staticmethod
    def _send_new_password_email(user: User, temp_password: str, reset_request: PasswordResetRequest) -> bool:
        """Send new password to user via email"""
        # Log that we're trying to send an email
        current_app.logger.info(f"Attempting to send password reset email to {user.email}")
        
        subject = "Your New Password - NutriKid"
        
        text_body = f"""
Dear {user.name},

Your password reset request has been approved. Here is your new temporary password:

Temporary Password: {temp_password}

IMPORTANT SECURITY NOTICE:
- This is a temporary password
- Please log in immediately and change your password
- Do not share this password with anyone
- This email should be deleted after you change your password

Login URL: {url_for('auth.login', _external=True)}

If you did not request this password reset, please contact your administrator immediately.

Best regards,
NutriKid Team
        """
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Your New Password</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #dc3545; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f8f9fa; }}
        .password-box {{ 
            background-color: #e9ecef; 
            border: 2px solid #007bff; 
            padding: 15px; 
            border-radius: 5px; 
            margin: 15px 0; 
            text-align: center;
            font-family: monospace;
            font-size: 18px;
            font-weight: bold;
        }}
        .warning {{ 
            background-color: #fff3cd; 
            border: 1px solid #ffeaa7; 
            padding: 15px; 
            border-radius: 5px; 
            margin: 15px 0; 
        }}
        .login-button {{ 
            display: inline-block; 
            padding: 15px 30px; 
            background-color: #007bff; 
            color: white; 
            text-decoration: none; 
            border-radius: 5px; 
            margin: 20px 0; 
            font-weight: bold;
        }}
        .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Password Reset Approved</h1>
        </div>
        <div class="content">
            <p>Dear {user.name},</p>
            <p>Your password reset request has been approved. Here is your new temporary password:</p>
            
            <div class="password-box">
                {temp_password}
            </div>
            
            <div class="warning">
                <h4>🔒 IMPORTANT SECURITY NOTICE:</h4>
                <ul>
                    <li>This is a <strong>temporary password</strong></li>
                    <li>Please log in immediately and change your password</li>
                    <li>Do not share this password with anyone</li>
                    <li>Delete this email after you change your password</li>
                </ul>
            </div>
            
            <div style="text-align: center;">
                <a href="{url_for('auth.login', _external=True)}" class="login-button">Login Now</a>
            </div>
            
            <p>If you did not request this password reset, please contact your administrator immediately.</p>
        </div>
        <div class="footer">
            <p>&copy; 2025 NutriKid Team</p>
        </div>
    </div>
</body>
</html>
        """
        
        result = EmailService.send_email(
            subject=subject,
            recipients=[user.email],
            text_body=text_body,
            html_body=html_body
        )
        
        # Log the result
        if result:
            current_app.logger.info(f"Successfully sent password reset email to {user.email}")
        else:
            current_app.logger.error(f"Failed to send password reset email to {user.email}")
            
        return result
    
    @staticmethod
    def get_pending_requests_for_admin(admin_user: User) -> List[PasswordResetRequest]:
        """Get pending password reset requests for an admin"""
        try:
            if admin_user.role == 'super_admin':
                # Super admin sees admin requests
                # Using filter_by instead of filter to avoid linter issues
                from sqlalchemy import text
                return (PasswordResetRequest.query
                        .join(User, text("password_reset_requests.user_id = user.id"))
                        .filter(text("password_reset_requests.status = 'pending'"))
                        .filter(User.role == 'admin')
                        .order_by(PasswordResetRequest.created_at.desc())
                        .all())
            elif admin_user.role == 'admin':
                # Admin sees student requests from their school
                from sqlalchemy import text
                return (PasswordResetRequest.query
                        .join(User, text("password_reset_requests.user_id = user.id"))
                        .filter(text("password_reset_requests.status = 'pending'"))
                        .filter(User.role == 'student')
                        .filter(User.school_id == admin_user.school_id)
                        .order_by(PasswordResetRequest.created_at.desc())
                        .all())
            else:
                return []
        except Exception as e:
            current_app.logger.error(f"Error in get_pending_requests_for_admin: {str(e)}")
            import traceback
            current_app.logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    @staticmethod
    def get_all_requests_for_admin(admin_user: User, limit: int = 50) -> List[PasswordResetRequest]:
        """Get all password reset requests for an admin (with limit)"""
        try:
            if admin_user.role == 'super_admin':
                # Super admin sees all requests
                from sqlalchemy import text
                return (PasswordResetRequest.query
                        .join(User, text("password_reset_requests.user_id = user.id"))
                        .order_by(PasswordResetRequest.created_at.desc())
                        .limit(limit)
                        .all())
            elif admin_user.role == 'admin':
                # Admin sees requests from their school
                from sqlalchemy import text
                return (PasswordResetRequest.query
                        .join(User, text("password_reset_requests.user_id = user.id"))
                        .filter(User.school_id == admin_user.school_id)
                        .order_by(PasswordResetRequest.created_at.desc())
                        .limit(limit)
                        .all())
            else:
                return []
        except Exception as e:
            current_app.logger.error(f"Error in get_all_requests_for_admin: {str(e)}")
            import traceback
            current_app.logger.error(f"Traceback: {traceback.format_exc()}")
            return []
        
    @staticmethod
    def cleanup_expired_requests() -> int:
        """Clean up expired password reset requests"""
        try:
            # Using raw SQL to avoid linter issues
            from sqlalchemy import text
            expired_requests = (PasswordResetRequest.query
                               .filter_by(status='pending')
                               .filter(text("expires_at < :current_time"))
                               .params(current_time=datetime.utcnow())
                               .all())
            
            for request in expired_requests:
                request.status = 'expired'
            
            db.session.commit()
            return len(expired_requests)
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error cleaning up expired requests: {str(e)}")
            return 0

    @staticmethod
    def clear_all_requests() -> int:
        """Remove all password reset requests (super admin action)"""
        try:
            deleted = PasswordResetRequest.query.delete()
            db.session.commit()
            return deleted or 0
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error clearing all requests: {str(e)}")
            return 0