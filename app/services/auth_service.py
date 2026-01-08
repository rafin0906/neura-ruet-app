# Auth service
from app.models.user import User
from app.core.security import verify_password, get_password_hash

def authenticate_user(username: str, password: str):
    # Placeholder for user authentication logic
    pass

def create_user(username: str, password: str):
    hashed_password = get_password_hash(password)
    user = User(username=username, hashed_password=hashed_password)
    return user