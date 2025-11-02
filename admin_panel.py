# admin_panel.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Patient, Doctor, Prediction, Appointment
from decorators import admin_required


admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')
# --- User Management ---

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@admin_required()
def get_all_users():
    """Admin: Get a list of all users."""
    try:
        # Query to get related Patient/Doctor details easily
        users_query = db.session.query(User, Patient, Doctor)\
            .outerjoin(Patient, User.id == Patient.user_id)\
            .outerjoin(Doctor, User.id == Doctor.user_id)\
            .order_by(User.full_name).all()

        user_list = []
        for user, patient, doctor in users_query:
            user_data = {
                'id': user.id,
                'full_name': user.full_name,
                'email': user.email,
                'role': user.role,
                'created_at': user.created_at.strftime("%Y-%m-%d"),
                'details': {}
            }
            if patient:
                user_data['details']['age'] = patient.age
                user_data['details']['gender'] = patient.gender
            if doctor:
                user_data['details']['specialization'] = doctor.specialization
            user_list.append(user_data)
        
        return jsonify(user_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
@admin_required()
def delete_user(user_id):
    """Admin: Delete a user."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Prevent an admin from deleting themselves
    current_admin_id = int(get_jwt_identity())
    if user.id == current_admin_id:
        return jsonify({'error': 'Admin cannot delete themselves'}), 403

    try:
        # 'cascade="all, delete-orphan"' in your User model
        # will handle deleting associated data.
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': f'User {user.full_name} and all associated data deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# --- NEW: Get full details for one user (for the edit modal) ---
@admin_bp.route('/user/<int:user_id>', methods=['GET'])
@jwt_required()
@admin_required()
def get_user_details(user_id):
    """Admin: Get full registration details for a single user."""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        user_data = {
            'id': user.id,
            'full_name': user.full_name,
            'email': user.email,
            'role': user.role,
        }

        if user.role == 'patient':
            patient_details = Patient.query.filter_by(user_id=user.id).first()
            if patient_details:
                user_data['age'] = patient_details.age
                user_data['gender'] = patient_details.gender
                user_data['phone'] = patient_details.phone
        elif user.role == 'doctor':
            doctor_details = Doctor.query.filter_by(user_id=user.id).first()
            if doctor_details:
                user_data['specialization'] = doctor_details.specialization
                user_data['experience_years'] = doctor_details.experience_years
                user_data['clinic_address'] = doctor_details.clinic_address

        return jsonify(user_data), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- MODIFIED: Replaced update_user_role with update_user_details ---
@admin_bp.route('/user/<int:user_id>', methods=['PUT'])
@jwt_required()
@admin_required()
def update_user_details(user_id):
    """Admin: Update a user's full registration info."""
    from app import bcrypt
    data = request.get_json()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    try:
        # Update User table
        user.full_name = data.get('full_name', user.full_name)
        user.email = data.get('email', user.email)
        
        # Check if password is being updated
        if data.get('password'): # Only update password if a new one is provided
            user.password_hash = bcrypt.generate_password_hash(data['password']).decode('utf-8')
        
        # Update role-specific tables
        if user.role == 'patient':
            patient_details = Patient.query.filter_by(user_id=user.id).first()
            if patient_details:
                patient_details.age = data.get('age')
                patient_details.gender = data.get('gender')
                patient_details.phone = data.get('phone')
        
        elif user.role == 'doctor':
            doctor_details = Doctor.query.filter_by(user_id=user.id).first()
            if doctor_details:
                doctor_details.specialization = data.get('specialization')
                doctor_details.experience_years = data.get('experience_years')
                doctor_details.clinic_address = data.get('clinic_address')

        db.session.commit()
        return jsonify({'message': f'User {user.full_name} updated successfully'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# --- Data Oversight ---

# --- NEW: Get all patients (read-only) ---
@admin_bp.route('/patients', methods=['GET'])
@jwt_required()
@admin_required()
def get_all_patients():
    """Admin: Get a list of all patients and their details."""
    try:
        patients = db.session.query(User, Patient)\
            .join(Patient, User.id == Patient.user_id)\
            .filter(User.role == 'patient')\
            .order_by(User.full_name).all()

        patient_list = [
            {
                'id': u.id,
                'full_name': u.full_name,
                'email': u.email,
                'age': p.age,
                'gender': p.gender,
                'phone': p.phone
            } for u, p in patients
        ]
        return jsonify(patient_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- NEW: Get all doctors (read-only) ---
@admin_bp.route('/doctors', methods=['GET'])
@jwt_required()
@admin_required()
def get_all_doctors():
    """Admin: Get a list of all doctors and their details."""
    try:
        doctors = db.session.query(User, Doctor)\
            .join(Doctor, User.id == Doctor.user_id)\
            .filter(User.role == 'doctor')\
            .order_by(User.full_name).all()

        doctor_list = [
            {
                'id': u.id,
                'full_name': u.full_name,
                'email': u.email,
                'specialization': d.specialization,
                'experience_years': d.experience_years,
                'clinic_address': d.clinic_address
            } for u, d in doctors
        ]
        return jsonify(doctor_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/predictions', methods=['GET'])
@jwt_required()
@admin_required()
def get_all_predictions():
    """Admin: Get all predictions from all users."""
    try:
        # Alias User model to be specific for the join
        PatientUser = db.aliased(User)
        
        preds = db.session.query(
            Prediction, PatientUser.full_name
        ).join(
            PatientUser, Prediction.user_id == PatientUser.id
        ).order_by(Prediction.timestamp.desc()).all()
        
        pred_list = [
            {
                'id': p.Prediction.id,
                'patient_name': p.full_name,
                'patient_id': p.Prediction.user_id,
                'result': p.Prediction.result,
                'probability': f"{p.Prediction.probability * 100:.2f}%",
                'timestamp': p.Prediction.timestamp.strftime("%Y-%m-%d %I:%M %p"),
                'doctor_note': p.Prediction.doctor_note
            } for p in preds
        ]
        return jsonify(pred_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/appointments', methods=['GET'])
@jwt_required()
@admin_required()
def get_all_appointments():
    """Admin: Get all appointments."""
    try:
        # Use aliased User models to join for both patient and doctor names
        User_patient = db.aliased(User)
        User_doctor = db.aliased(User)
        
        appts = db.session.query(
            Appointment.id,
            Appointment.appointment_datetime,
            Appointment.status,
            Appointment.reason,
            User_patient.full_name.label('patient_name'),
            User_doctor.full_name.label('doctor_name')
        ).join(
            User_patient, Appointment.patient_id == User_patient.id
        ).join(
            User_doctor, Appointment.doctor_id == User_doctor.id
        ).order_by(Appointment.appointment_datetime.desc()).all()
        
        appt_list = [
            {
                'id': a.id,
                'status': a.status,
                'datetime': a.appointment_datetime.strftime("%Y-%m-%d %I:%M %p"),
                'reason': a.reason,
                'patient_name': a.patient_name,
                'doctor_name': a.doctor_name
            } for a in appts
        ]
        return jsonify(appt_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

