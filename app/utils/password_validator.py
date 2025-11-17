import re
from typing import List, Tuple

class PasswordValidator:
    def __init__(self):
        self.common_sequences = [
            # Numeric sequences
            '0123456789', '9876543210',
            # Alphabetic sequences
            'abcdefghijklmnopqrstuvwxyz', 'zyxwvutsrqponmlkjihgfedcba',
            # Keyboard sequences
            'qwertyuiop', 'asdfghjkl', 'zxcvbnm',
            '1qaz2wsx', '1q2w3e4r'
        ]
        
        self.common_passwords = [
            'password', '123456', 'qwerty', 'admin', 'welcome',
            'letmein', 'monkey', 'dragon', 'baseball', 'football'
        ]

    def check_sequential_patterns(self, password: str) -> List[str]:
        """Check for sequential patterns in the password."""
        issues = []
        
        # Check for numeric sequences
        if re.search(r'(\d)\1{2,}', password):
            issues.append("Password contains repeated numbers")
            
        # Check for keyboard sequences
        for seq in self.common_sequences:
            if seq in password.lower():
                issues.append(f"Password contains a common sequence: {seq}")
                
        return issues

    def check_common_passwords(self, password: str) -> bool:
        """Check if the password is in the list of common passwords."""
        return password.lower() in self.common_passwords

    def validate_password(self, password: str) -> Tuple[bool, List[str]]:
        """Validate password strength and return (is_valid, issues)."""
        issues = []
        
        # Check minimum length
        if len(password) < 8:
            issues.append("Password must be at least 8 characters long")
            
        # Check for sequential patterns
        issues.extend(self.check_sequential_patterns(password))
        
        # Check for common passwords
        if self.check_common_passwords(password):
            issues.append("Password is too common and easily guessable")
            
        # Check for required character types
        if not re.search(r'\d', password):
            issues.append("Password must contain at least one number")
            
        return len(issues) == 0, issues