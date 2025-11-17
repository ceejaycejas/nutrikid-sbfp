from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.notification import Notification
from app.services.notification_service import NotificationService
from datetime import datetime

bp = Blueprint('notifications', __name__, url_prefix='/notifications')

@bp.route('/')
@login_required
def index():
    """Display all notifications for the current user"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    notifications = Notification.query.filter_by(recipient_id=current_user.id)\
                                    .order_by(Notification.created_at.desc())\
                                    .paginate(page=page, per_page=per_page, error_out=False)
    
    # Mark notifications as read when viewed
    unread_notifications = Notification.query.filter_by(
        recipient_id=current_user.id, 
        is_read=False
    ).all()
    
    for notification in unread_notifications:
        notification.mark_as_read()
    
    return render_template('notifications/index.html', notifications=notifications)

@bp.route('/api/unread-count')
@login_required
def get_unread_count():
    """API endpoint to get unread notification count"""
    count = Notification.get_unread_count(current_user.id)
    return jsonify({'count': count})

@bp.route('/api/recent')
@login_required
def get_recent():
    """API endpoint to get recent notifications"""
    limit = request.args.get('limit', 5, type=int)
    notifications = Notification.get_recent_notifications(current_user.id, limit)
    
    return jsonify({
        'notifications': [n.to_dict() for n in notifications],
        'unread_count': Notification.get_unread_count(current_user.id)
    })

@bp.route('/api/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_as_read(notification_id):
    """API endpoint to mark a notification as read"""
    success = NotificationService.mark_notification_as_read(notification_id, current_user.id)
    
    if success:
        return jsonify({'success': True, 'message': 'Notification marked as read'})
    else:
        return jsonify({'success': False, 'message': 'Notification not found'}), 404

@bp.route('/api/mark-all-read', methods=['POST'])
@login_required
def mark_all_as_read():
    """API endpoint to mark all notifications as read"""
    count = NotificationService.mark_all_as_read(current_user.id)
    
    return jsonify({
        'success': True, 
        'message': f'{count} notifications marked as read',
        'count': count
    })

@bp.route('/api/delete/<int:notification_id>', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    """API endpoint to delete a notification"""
    notification = Notification.query.filter_by(
        id=notification_id, 
        recipient_id=current_user.id
    ).first()
    
    if notification:
        db.session.delete(notification)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Notification deleted'})
    else:
        return jsonify({'success': False, 'message': 'Notification not found'}), 404

@bp.route('/settings')
@login_required
def settings():
    """Notification settings page"""
    return render_template('notifications/settings.html')

@bp.route('/test')
@login_required
def test_notification():
    """Test endpoint to create a sample notification (for development)"""
    if current_user.role not in ['super_admin', 'admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('notifications.index'))
    
    # Create different types of test notifications
    test_notifications = [
        {
            'title': 'Welcome to NutriKid!',
            'message': 'Your account has been successfully created. You can now access all features of the nutrition management system.',
            'type': 'account_created',
            'priority': 'high'
        },
        {
            'title': 'Profile Updated',
            'message': 'Your profile information has been updated successfully by an administrator.',
            'type': 'profile_updated',
            'priority': 'medium'
        },
        {
            'title': 'New Student Added',
            'message': 'A new student has been added to your section. Please review their nutritional requirements.',
            'type': 'student_added',
            'priority': 'low'
        },
        {
            'title': 'System Maintenance',
            'message': 'The system will undergo maintenance tonight from 2:00 AM to 4:00 AM. Some features may be temporarily unavailable.',
            'type': 'system_maintenance',
            'priority': 'medium'
        }
    ]
    
    for i, notif in enumerate(test_notifications):
        NotificationService.create_notification(
            recipient_id=current_user.id,
            title=notif['title'],
            message=notif['message'],
            notification_type=notif['type'],
            priority=notif['priority'],
            action_url=url_for('notifications.index'),
            action_text="View Details",
            send_email=False  # Don't send emails for test notifications
        )
    
    flash(f'{len(test_notifications)} test notifications created successfully!', 'success')
    return redirect(url_for('notifications.index'))