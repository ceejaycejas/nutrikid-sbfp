from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.school import School
from app.models.notification import Notification
from app.models.user_activity import UserActivity
from werkzeug.utils import secure_filename
import os
from datetime import datetime

def log_activity(user_id, activity_type, description, ip_address=None):
    activity = UserActivity(user_id=user_id, activity_type=activity_type, description=description, ip_address=ip_address)
    db.session.add(activity)
    db.session.commit()

bp = Blueprint('account', __name__, url_prefix='/account')

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    log_activity(current_user.id, 'view_settings', 'Accessed account settings page', request.remote_addr)
    if request.method == 'POST':
        # Handle profile image upload only
        if 'profile_image' in request.files and request.files['profile_image'].filename:
            try:
                file = request.files['profile_image']
                filename = secure_filename(file.filename)
                ext = os.path.splitext(filename)[1]
                # Add timestamp to ensure unique filename and prevent caching issues
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"user_{current_user.id}_{timestamp}{ext}"
                
                # Ensure the directory exists
                upload_dir = os.path.join('app', 'static', 'profile_images')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Delete old profile image if it exists
                if current_user.profile_image:
                    old_filepath = os.path.join('app', 'static', current_user.profile_image)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except:
                            pass  # Ignore if file doesn't exist
                
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                current_user.profile_image = f'profile_images/{filename}'
                db.session.commit()
                log_activity(current_user.id, 'update_profile', 'Updated profile picture', request.remote_addr)
                flash('Profile picture updated!', 'success')
                return redirect(url_for('account.settings'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error uploading profile picture: {str(e)}', 'danger')
                return redirect(url_for('account.settings'))
        # Handle cover image upload only
        if 'cover_image' in request.files and request.files['cover_image'].filename:
            try:
                file = request.files['cover_image']
                filename = secure_filename(file.filename)
                ext = os.path.splitext(filename)[1]
                # Add timestamp to ensure unique filename and prevent caching issues
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"cover_{current_user.id}_{timestamp}{ext}"
                
                # Ensure the directory exists
                upload_dir = os.path.join('app', 'static', 'profile_images')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Delete old cover image if it exists
                if current_user.cover_image:
                    old_filepath = os.path.join('app', 'static', current_user.cover_image)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except:
                            pass  # Ignore if file doesn't exist
                
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                current_user.cover_image = f'profile_images/{filename}'
                db.session.commit()
                log_activity(current_user.id, 'update_profile', 'Updated cover image', request.remote_addr)
                flash('Cover image updated!', 'success')
                return redirect(url_for('account.settings'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error uploading cover image: {str(e)}', 'danger')
                return redirect(url_for('account.settings'))
        # Handle main profile info update
        if 'name' in request.form and 'email' in request.form:
            current_user.name = request.form.get('name')
            current_user.email = request.form.get('email')
            # Update password if provided
            new_password = request.form.get('new_password')
            if new_password:
                current_password = request.form.get('current_password')
                if current_user.check_password(current_password):
                    current_user.set_password(new_password)
                    log_activity(current_user.id, 'password_change', 'Changed account password', request.remote_addr)
                else:
                    log_activity(current_user.id, 'password_change_failed', 'Failed password change attempt - incorrect current password', request.remote_addr)
                    flash('Current password is incorrect', 'danger')
                    return redirect(url_for('account.settings'))
            # Update school information if admin
            if current_user.role == 'admin':
                school = School.query.get(current_user.school_id)
                if school:
                    school.name = request.form.get('school_name')
                    school.address = request.form.get('school_address')
            try:
                db.session.commit()
                log_activity(current_user.id, 'update_profile', 'Updated account information', request.remote_addr)
                flash('Your account has been updated successfully!', 'success')
            except:
                db.session.rollback()
                flash('An error occurred while updating your account.', 'danger')
    school = School.query.get(current_user.school_id) if current_user.school_id else None
    return render_template('account/settings.html', school=school)

@bp.route('/notifications')
@login_required
def notifications():
    log_activity(current_user.id, 'view_notifications', 'Accessed notifications page', request.remote_addr)
    notifs = Notification.query.filter_by(recipient_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('account/notifications.html', notifications=notifs)

@bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.recipient_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('account.notifications'))
    notif.is_read = True
    db.session.commit()
    flash('Notification marked as read.', 'success')
    return redirect(url_for('account.notifications'))

@bp.route('/notifications/<int:notif_id>/delete', methods=['POST'])
@login_required
def delete_notification(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.recipient_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('account.notifications'))
    db.session.delete(notif)
    db.session.commit()
    flash('Notification deleted.', 'success')
    return redirect(url_for('account.notifications')) 