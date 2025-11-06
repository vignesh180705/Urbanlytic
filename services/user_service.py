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

    def validate_profile_update(self, username, data):
        errors = {}
        existing_user = self.repo.get_user_by_email(data["email"])
        if existing_user and existing_user["username"] != username:
            errors["mailError"] = True
        if not re.match(r"[^@]+@[^@]+\.[^@]+", data["email"]):
            errors["mailNotValidError"] = True
        if not data["phone"].isdigit() or len(data["phone"]) < 10:
            errors["phoneError"] = True
        return errors

    def update_profile(self, username, data):
        errors = self.validate_profile_update(username, data)
        if errors:
            return {"status": "error", "errors": errors}
        self.repo.update_user(username, {
            "name": data["name"],
            "email": data["email"],
            "phone": data["phone"],
            "updated_at": datetime.utcnow()
        })
        return {"status": "success", "message": "Profile updated successfully"}

    def validate_password_change(self, current_username, current_password, new_password, confirm_password):
        errors = {}
        user = self.repo.get_user_by_username(current_username)
        if not user or not check_password_hash(user["password"], current_password):
            errors["currentPassError"] = True
        if new_password != confirm_password:
            errors["passError"] = True
        if len(new_password) < 8:
            errors["lengthError"] = True
        if not re.search(r"[A-Z]", new_password):
            errors["upperCaseError"] = True
        if not re.search(r"[a-z]", new_password):
            errors["lowerCaseError"] = True
        if not re.search(r"[0-9]", new_password):
            errors["numberError"] = True
        if not re.search(r"[@$!%*?&#]", new_password):
            errors["specialCharError"] = True
        return errors

    def change_password(self, username, current_password, new_password, confirm_password):
        errors = self.validate_password_change(username, current_password, new_password, confirm_password)
        if errors:
            return {"status": "error", "errors": errors}
        hashed_pw = generate_password_hash(new_password)
        self.repo.update_user(username, {"password": hashed_pw, "updated_at": datetime.utcnow()})
        return {"status": "success", "message": "Password changed successfully"}
