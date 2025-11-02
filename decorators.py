from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity,jwt_required
from models import User


# Generic role-based decorator factory
def role_required(required_role):
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorator(*args, **kwargs):
            try:
                current_user_id = get_jwt_identity()
                if not current_user_id:
                    return jsonify({"message": "Missing JWT identity"}), 401
                user = User.query.get(int(current_user_id))
                if user and user.role == required_role:
                    return fn(*args, **kwargs)
                return jsonify({"message": f"{required_role.capitalize()} access required"}), 403
            except Exception as e:
                return jsonify({"message": f"Role check failed: {str(e)}"}), 500
        return decorator
    return wrapper


def admin_required():
    return role_required('admin')


def doctor_required():
    return role_required('doctor')