"""
Security utilities for the Due Diligence Platform
"""
import os
import secrets
import hashlib
import hmac
from functools import wraps
from flask import request, jsonify, current_app
import time
from collections import defaultdict
import re

class SecurityManager:
    def __init__(self):
        self.rate_limit_storage = defaultdict(list)
        self.blocked_ips = set()
        
    def validate_input(self, input_string, max_length=1000, allow_special_chars=True):
        """Validate and sanitize user input"""
        if not input_string:
            return ""
        
        # Remove null bytes and control characters
        cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', str(input_string))
        
        # Limit length
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length]
        
        # If special characters not allowed, remove them
        if not allow_special_chars:
            cleaned = re.sub(r'[<>"\';()&+]', '', cleaned)
        
        return cleaned.strip()
    
    def validate_symbol(self, symbol):
        """Validate stock symbol format"""
        if not symbol:
            return False
        
        # Stock symbols should be alphanumeric, 1-5 characters typically
        pattern = r'^[A-Za-z0-9]{1,10}$'
        return bool(re.match(pattern, symbol))
    
    def rate_limit(self, max_requests=10, window_minutes=1):
        """Rate limiting decorator"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
                
                if client_ip in self.blocked_ips:
                    return jsonify({'error': 'IP blocked due to abuse'}), 429
                
                current_time = time.time()
                window_start = current_time - (window_minutes * 60)
                
                # Clean old requests
                self.rate_limit_storage[client_ip] = [
                    req_time for req_time in self.rate_limit_storage[client_ip]
                    if req_time > window_start
                ]
                
                # Check rate limit
                if len(self.rate_limit_storage[client_ip]) >= max_requests:
                    # Block IP if consistently hitting rate limits
                    if len(self.rate_limit_storage[client_ip]) > max_requests * 2:
                        self.blocked_ips.add(client_ip)
                    
                    return jsonify({
                        'error': 'Rate limit exceeded',
                        'retry_after': window_minutes * 60
                    }), 429
                
                # Add current request
                self.rate_limit_storage[client_ip].append(current_time)
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    def validate_api_key(self, api_key, service_name):
        """Validate API key format (basic validation)"""
        if not api_key or api_key.startswith('your_'):
            return False, f"Please configure a valid {service_name} API key"
        
        # Basic format validation
        if len(api_key) < 10:
            return False, f"Invalid {service_name} API key format"
        
        return True, "Valid"
    
    def secure_headers(self, response):
        """Add security headers to response"""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        return response
    
    def log_security_event(self, event_type, details, client_ip=None):
        """Log security events"""
        if not client_ip:
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] SECURITY: {event_type} - IP: {client_ip} - {details}"
        
        # In production, this should go to a proper logging system
        print(log_entry)
    
    def check_suspicious_activity(self, user_input):
        """Check for suspicious patterns in user input"""
        suspicious_patterns = [
            r'<script',
            r'javascript:',
            r'on\w+\s*=',
            r'eval\s*\(',
            r'document\.',
            r'window\.',
            r'\.\./',
            r'union\s+select',
            r'drop\s+table',
            r'insert\s+into',
            r'delete\s+from'
        ]
        
        user_input_lower = user_input.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, user_input_lower):
                return True, f"Suspicious pattern detected: {pattern}"
        
        return False, "Clean"

# Global security manager instance
security_manager = SecurityManager()

def require_valid_input(field_name, max_length=1000, allow_special_chars=True):
    """Decorator to validate specific input fields"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json() if request.is_json else request.form
            
            if field_name not in data:
                return jsonify({'error': f'Missing required field: {field_name}'}), 400
            
            value = data[field_name]
            
            # Check for suspicious activity
            is_suspicious, reason = security_manager.check_suspicious_activity(str(value))
            if is_suspicious:
                security_manager.log_security_event(
                    'SUSPICIOUS_INPUT',
                    f"Field: {field_name}, Reason: {reason}, Value: {str(value)[:100]}"
                )
                return jsonify({'error': 'Invalid input detected'}), 400
            
            # Validate and sanitize
            cleaned_value = security_manager.validate_input(
                value, max_length, allow_special_chars
            )
            
            # Update request data with cleaned value
            if request.is_json:
                request.json[field_name] = cleaned_value
            else:
                request.form = request.form.copy()
                request.form[field_name] = cleaned_value
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_symbol_input(f):
    """Decorator specifically for stock symbol validation"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if symbol is in URL path
        if 'symbol' in kwargs:
            symbol = kwargs['symbol']
        else:
            # Check in request data
            data = request.get_json() if request.is_json else request.form
            symbol = data.get('symbol', '')
        
        if not security_manager.validate_symbol(symbol):
            security_manager.log_security_event(
                'INVALID_SYMBOL',
                f"Invalid symbol format: {symbol}"
            )
            return jsonify({'error': 'Invalid symbol format'}), 400
        
        return f(*args, **kwargs)
    return decorated_function

