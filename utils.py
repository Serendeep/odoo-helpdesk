from functools import wraps
import hashlib
import logging
from flask import request, abort
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
import json
import time
from cachetools import TTLCache
import os

from services import verify_customer

# Load secret key from environment variable
SECRET_KEY = os.getenv("cmo_decryption_key")

# Cache for verified customers
customer_cache = TTLCache(maxsize=1000, ttl=3600)  # Cache for 1 hour

def decrypt_data(token, secret_key):
    """Decrypts the token using AES-256 CBC mode with the provided secret key."""
    try:
        token_bytes = base64.b64decode(token)
        iv, encrypted_data = token_bytes[:16], token_bytes[16:]
        
        key = hashlib.sha512(secret_key.encode()).hexdigest()[:32].encode('utf-8')
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
        unpadded = decrypted_data[:-decrypted_data[-1]]  # Remove padding
        
        json_data = json.loads(unpadded.decode('utf-8'))
        logging.info(f"Successfully decrypted data : {json_data}")
        return json.loads(unpadded.decode('utf-8'))
    except Exception as e:
        logging.error(f"Error during decryption: {e}")
        raise ValueError("Invalid or corrupt token.")

def check_token_expiry(token_created_at, token_expires_in):
    """Checks if the token has expired based on creation time and expiry period."""
    current_time = int(time.time())
    expiry_time = token_created_at + (token_expires_in * 60)
    
    if current_time > expiry_time:
        raise ValueError('Token has expired.')

def verify_customer_cached(email, company_id):
    """Checks if the customer is verified, using cached data to improve performance."""
    cache_key = f"{email}:{company_id}"
    
    if cache_key not in customer_cache:
        is_verified = verify_customer(email, company_id)
        customer_cache[cache_key] = is_verified
    
    return customer_cache[cache_key]

def extract_bearer_token(auth_header):
    """Extracts the Bearer token from the Authorization header."""
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(' ', 1)[1]
    return None

def auth_required(f):
    """Decorator to enforce token-based authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        bearer_token = extract_bearer_token(auth_header)
        
        if not bearer_token:
            abort(401, 'Malformed or missing Bearer token.')
        
        try:
            decrypted_data = decrypt_data(bearer_token, SECRET_KEY)
            
            check_token_expiry(decrypted_data['token_created_at'], decrypted_data['token_expires_in'])
            
            if not verify_customer_cached(decrypted_data['email'], decrypted_data['company_id']):
                raise ValueError('Invalid customer.')
            
            # Attach decrypted data to the request for downstream use
            request.decrypted_data = decrypted_data
            return f(*args, **kwargs)
        except ValueError as e:
            logging.warning(f"Authentication error: {e}")
            abort(401, str(e))
        except Exception as e:
            logging.error(f"Unexpected error during authentication: {e}")
            abort(500, 'Internal server error')
    
    return decorated_function
