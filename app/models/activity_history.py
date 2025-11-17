from datetime import datetime
from db import create_connection

class ActivityHistory:
    def __init__(self):
        self.connection = create_connection()

    def record_activity(self, user_id, activity_type, description, details=None):
        """
        Record a user activity in the history
        
        Args:
            user_id (int): The ID of the user performing the activity
            activity_type (str): Type of activity (e.g., 'login', 'update_profile', 'add_child', etc.)
            description (str): Description of the activity
            details (dict, optional): Additional details about the activity
        """
        try:
            cursor = self.connection.cursor()
            
            # Create activity_history table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    activity_type VARCHAR(50) NOT NULL,
                    description TEXT NOT NULL,
                    details JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Insert the activity record
            cursor.execute("""
                INSERT INTO activity_history (user_id, activity_type, description, details)
                VALUES (%s, %s, %s, %s)
            """, (user_id, activity_type, description, str(details) if details else None))
            
            self.connection.commit()
            return True
            
        except Exception as e:
            print(f"Error recording activity: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_user_activities(self, user_id, limit=50):
        """
        Retrieve activity history for a specific user
        
        Args:
            user_id (int): The ID of the user
            limit (int): Maximum number of records to return
            
        Returns:
            list: List of activity records
        """
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM activity_history 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (user_id, limit))
            
            return cursor.fetchall()
            
        except Exception as e:
            print(f"Error retrieving activities: {e}")
            return []
        finally:
            if cursor:
                cursor.close()

    def get_all_activities(self, limit=100):
        """
        Retrieve all activity history
        
        Args:
            limit (int): Maximum number of records to return
            
        Returns:
            list: List of activity records
        """
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT ah.*, COALESCE(u.name, u.email) as username 
                FROM activity_history ah
                JOIN users u ON ah.user_id = u.id
                ORDER BY ah.created_at DESC 
                LIMIT %s
            """, (limit,))
            
            return cursor.fetchall()
            
        except Exception as e:
            print(f"Error retrieving activities: {e}")
            return []
        finally:
            if cursor:
                cursor.close()

    def __del__(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()