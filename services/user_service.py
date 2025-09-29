import re
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from repository.user_repository import UserRepository

class UserService:
    def __init__(self):
        self.repo = UserRepository()

    def validate_registration(self, data):
        errors = {}
        if self.repo.get_user_by_username(data["username"]):
            errors["userError"] = True
        if data["password"] != data["confirm_password"]:
            errors["passError"] = True
        if len(data["password"]) < 8:
            errors["lengthError"] = True
        if not re.search(r"[A-Z]", data["password"]):
            errors["upperCaseError"] = True
        if not re.search(r"[a-z]", data["password"]):
            errors["lowerCaseError"] = True
        if not re.search(r"[0-9]", data["password"]):
            errors["numberError"] = True
        if not re.search(r"[@$!%*?&#]", data["password"]):
            errors["specialCharError"] = True
        if not data["phone"].isdigit() or len(data["phone"]) < 10:
            errors["phoneError"] = True
        if not re.match(r"[^@]+@[^@]+\.[^@]+", data["email"]):
            errors["mailNotValidError"] = True
        if self.repo.get_user_by_email(data["email"]):
            errors["mailError"] = True

        return errors

    def register_user(self, data):
        hashed_pw = generate_password_hash(data["password"])
        user_dict = {
            "name": data["name"],
            "username": data["username"],
            "email": data["email"],
            "phone": data["phone"],
            "password": hashed_pw,
            "created_at": datetime.utcnow()
        }
        self.repo.save_user(user_dict)

    def authenticate_user(self, username, password):
        user = self.repo.get_user_by_username(username)
        if not user:
            return None, "User not found"
        if not check_password_hash(user["password"], password):
            return None, "Invalid password"
        return user, None
