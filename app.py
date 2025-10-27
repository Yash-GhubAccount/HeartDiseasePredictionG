import flask
from flask import request, jsonify, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, JWTManager
import joblib
import pandas as pd
import os
import traceback
import json
from datetime import datetime , timezone

# --- 1. INITIALIZE FLASK APP & EXTENSIONS ---
app = flask.Flask(__name__)
CORS(app)

# --- App Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'cardiocare.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["JWT_SECRET_KEY"] = "your-super-secret-key-change-me" # Change this in production!

# --- Initialize Extensions ---
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# --- 3. SERVE THE FRONTEND ---
@app.route('/')
def home():
    return render_template('index.html')

# --- 2. DEFINE DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), nullable=False) # 'patient' or 'doctor'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient_details = db.relationship('Patient', backref='user', uselist=False, cascade="all, delete-orphan")
    doctor_details = db.relationship('Doctor', backref='user', uselist=False, cascade="all, delete-orphan")
    predictions = db.relationship('Prediction', backref='user', lazy=True, cascade="all, delete-orphan")
    # Relationships for appointments
    patient_appointments = db.relationship('Appointment', foreign_keys='Appointment.patient_id', backref='patient', lazy=True)
    doctor_appointments = db.relationship('Appointment', foreign_keys='Appointment.doctor_id', backref='doctor', lazy=True)


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    specialization = db.Column(db.String(100), nullable=True)
    experience_years = db.Column(db.Integer, nullable=True)
    clinic_address = db.Column(db.String(200), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    result = db.Column(db.String(10), nullable=False) # 'Yes' or 'No'
    probability = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    input_data = db.Column(db.Text, nullable=False) # Store input features as JSON string
    recommendations = db.relationship('Recommendation', backref='prediction', lazy=True, cascade="all, delete-orphan")
    doctor_note = db.Column(db.Text, nullable=True) # To store doctor's private notes

class Recommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    prediction_id = db.Column(db.Integer, db.ForeignKey('prediction.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# NEW: Appointment Model
class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appointment_datetime = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Pending') # Pending, Approved, Rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# --- 3. LOAD ML MODELS & THRESHOLDS ---
MODEL_DIR = 'models'
try:
    lr_pipeline = joblib.load(os.path.join(MODEL_DIR, "logreg_pipeline.pkl"))
    xgb_pipeline = joblib.load(os.path.join(MODEL_DIR, "xgb_pipeline.pkl"))
    thresholds = joblib.load(os.path.join(MODEL_DIR, "best_thresholds.pkl"))
    print("Models and thresholds loaded successfully.")
except FileNotFoundError:
    print("Error: Model files not found. Please run the model_trainer.py script first.")
    lr_pipeline = xgb_pipeline = thresholds = None

# --- 4. AUTHENTICATION API ENDPOINTS ---
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data or 'full_name' not in data or 'role' not in data:
        return jsonify({"message": "Missing required fields"}), 400
    email = data.get('email')
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already registered"}), 409
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    new_user = User(full_name=data['full_name'], email=email, password_hash=hashed_password, role=data['role'])
    db.session.add(new_user)
    db.session.flush() # Flush to get the user ID before creating patient/doctor
    if data['role'] == 'patient':
        new_patient = Patient(age=data.get('age'), gender=data.get('gender'), phone=data.get('phone'), user_id=new_user.id)
        db.session.add(new_patient)
    elif data['role'] == 'doctor':
        new_doctor = Doctor(specialization=data.get('specialization'), experience_years=data.get('experience_years'), clinic_address=data.get('clinic_address'), user_id=new_user.id)
        db.session.add(new_doctor)
    db.session.commit()
    return jsonify({"message": "User registered successfully"}), 201

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
         return jsonify({"message": "Missing email or password"}), 400
    email = data.get('email')
    password = data.get('password')
    user = User.query.filter_by(email=email).first()
    if user and bcrypt.check_password_hash(user.password_hash, password):
        # Use user ID as string for JWT identity
        access_token = create_access_token(identity=str(user.id))
        return jsonify(access_token=access_token, userRole=user.role), 200
    return jsonify({"message": "Invalid credentials"}), 401

# --- 5. PREDICTION, HISTORY, RECOMMENDATIONS API ENDPOINTS ---
def generate_recommendations(user_inputs, prediction_result):
    recommendations = []
    if prediction_result == "Yes":
        recommendations.append("It is highly recommended to consult a healthcare professional to discuss these results.")
    else:
        recommendations.append("Continue to maintain a healthy lifestyle and schedule regular checkups with your doctor.")
    if user_inputs.get('Smoking_History') == 'Yes':
        recommendations.append("Quitting smoking is one of the most impactful steps you can take to improve cardiovascular health.")
    if user_inputs.get('BMI') is not None:
         try:
            bmi_float = float(user_inputs.get('BMI', 0))
            if bmi_float >= 25.0:
                recommendations.append("Aiming for a BMI below 25 can significantly reduce heart disease risk.")
            if bmi_float < 18.5:
                 recommendations.append("Your BMI is low. Consult a doctor or nutritionist for advice on maintaining a healthy weight.")
         except ValueError:
             print(f"Could not convert BMI value '{user_inputs.get('BMI')}' to float.") # Log error
    if user_inputs.get('Exercise') == 'No':
         recommendations.append("Incorporating regular exercise, like 30 minutes of moderate activity most days, is beneficial for heart health.")
    # Add more rules as needed
    return recommendations

@app.route("/api/predict", methods=["POST"])
@jwt_required()
def predict():
    # Check if models are loaded (this is from your original code)
    if not all([lr_pipeline, xgb_pipeline, thresholds]):
        return jsonify({"message": "ML models are not loaded. Server setup is incomplete."}), 500
    
    json_data = None # Define here so 'except' block can access it
    try:
        user_id = int(get_jwt_identity())
        json_data = request.get_json()

        if not json_data:
             return jsonify({"message": "No input data provided."}), 400

        # --- FIX ---
        # Create the DataFrame directly from the raw form data.
        # The new model pipelines handle all preprocessing.
        input_df = pd.DataFrame([json_data])
        # --- END FIX ---
        
        # --- Model Prediction ---
        probs_lr = lr_pipeline.predict_proba(input_df)[:, 1]
        probs_xgb = xgb_pipeline.predict_proba(input_df)[:, 1]
        
        weighted_avg_prob = (0.3 * probs_lr) + (0.7 * probs_xgb)
        
        if 'weighted_average' not in thresholds:
            print("Error: 'weighted_average' key not found in best_thresholds.pkl")
            return jsonify({'message': 'Server configuration error: Missing threshold.'}), 500
            
        threshold = thresholds['weighted_average']
        prediction_value = (weighted_avg_prob >= threshold).astype(int)[0]
        prediction_result = "Yes" if prediction_value == 1 else "No"
        probability_score = weighted_avg_prob[0]
        
        # --- Recommendations & Database ---
        # Pass the original string data to recommendations
        recommendation_list = generate_recommendations(json_data, prediction_result)

        new_prediction = Prediction(result=prediction_result, probability=probability_score, user_id=user_id, input_data=json.dumps(json_data))
        db.session.add(new_prediction)
        db.session.commit()

        response = {
            'prediction': prediction_result,
            'probability': f"{probability_score * 100:.2f}%",
            'recommendations': recommendation_list
        }
        return jsonify(response)
    
    except (ValueError, TypeError) as ve:
        # Catches bad data from the form or format mismatches for the model
        # (This is where the 'ufunc isnan' error would be caught)
        print("\n--- PREDICTION DATA ERROR ---")
        print(f"Error: {ve}")
        print(f"Data received: {json_data}")
        print(traceback.format_exc()) # Log the full stack trace
        print("-----------------------------\n")
        db.session.rollback() # Rollback any partial DB changes
        return jsonify({'message': 'Invalid input data. Please check the form and try again.'}), 400

    except Exception as e:
        # Catches all other unexpected errors (e.g., DB failure)
        print("\n--- UNEXPECTED PREDICTION ERROR ---")
        print(f"Error: {e}")
        print(traceback.format_exc()) # Log the full stack trace
        print("-----------------------------------\n")
        db.session.rollback() # Rollback any partial DB changes
        return jsonify({'message': f"An unexpected server error occurred."}), 500

@app.route("/api/history", methods=["GET"])
@jwt_required()
def get_history():
    try:
        user_id = int(get_jwt_identity())
        predictions = Prediction.query.filter_by(user_id=user_id).order_by(Prediction.timestamp.desc()).all()
        history_list = [{'id': p.id, 'result': p.result, 'probability': f"{p.probability * 100:.2f}%", 'timestamp': p.timestamp.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime("%Y-%m-%d %I:%M %p")} for p in predictions]
        return jsonify(history_list), 200
    except Exception as e:
        print(f"History Fetch Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recommendations', methods=['GET'])
@jwt_required()
def get_recommendations():
    current_user = get_jwt_identity()

    predictions = Prediction.query.filter_by(user_id=current_user).order_by(Prediction.timestamp.desc()).all()
    output = []

    for pred in predictions:
        # Assuming you store input_data as JSON string in Prediction
        try:
            user_inputs = json.loads(pred.input_data)
        except Exception:
            user_inputs = {}

        recs = generate_recommendations(user_inputs, pred.result)
        output.append({
            "timestamp": pred.timestamp.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime("%Y-%m-%d %I:%M %p"),
            "result": pred.result,
            "recommendations": recs
        })

    return jsonify(output), 200

# --- 6. APPOINTMENT API ENDPOINTS ---

# Endpoint for patients to get a list of doctors
@app.route("/api/doctors", methods=["GET"])
@jwt_required()
def get_doctors():
    try:
        # Join User and Doctor tables to get name and specialization
        doctors = db.session.query(
            User.id,
            User.full_name,
            Doctor.specialization
        ).join(Doctor, User.id == Doctor.user_id).filter(User.role == 'doctor').all()
        
        # Format the name including specialization
        doctor_list = [{"id": doc.id, "name": f"{doc.full_name} ({doc.specialization or 'General'})"} for doc in doctors]
        return jsonify(doctor_list), 200
    except Exception as e:
        print(f"Get Doctors Error: {e}")
        return jsonify({'error': str(e)}), 500

# Endpoint for patients to book an appointment
@app.route("/api/appointments", methods=["POST"])
@jwt_required()
def book_appointment():
    try:
        user_id = int(get_jwt_identity()) # This is the patient's ID
        data = request.get_json()
        
        doctor_id_str = data.get('doctor_id')
        datetime_str = data.get('datetime')
        reason = data.get('reason')

        if not doctor_id_str or not datetime_str:
            return jsonify({'error': 'Doctor and datetime are required'}), 400
        
        try:
            doctor_id = int(doctor_id_str)
        except ValueError:
             return jsonify({'error': 'Invalid Doctor ID format'}), 400

        # Validate doctor exists
        doctor = User.query.filter_by(id=doctor_id, role='doctor').first()
        if not doctor:
            return jsonify({'error': 'Selected doctor not found'}), 404

        # Convert datetime string to Python datetime object
        try:
            # Format from datetime-local input: "YYYY-MM-DDTHH:MM"
            appointment_dt = datetime.fromisoformat(datetime_str)
            # Basic validation: ensure date is in the future
            if appointment_dt <= datetime.now():
                 return jsonify({'error': 'Appointment date must be in the future'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid datetime format. Use YYYY-MM-DDTHH:MM'}), 400

        new_appointment = Appointment(
            patient_id=user_id,
            doctor_id=doctor_id,
            appointment_datetime=appointment_dt,
            reason=reason # Will be None if not provided, which is okay
        )
        db.session.add(new_appointment)
        db.session.commit()
        
        return jsonify({'message': 'Appointment requested successfully'}), 201

    except Exception as e:
        db.session.rollback()
        print(f"Book Appointment Error: {e}")
        return jsonify({'error': str(e)}), 500
    

# Endpoint for patients to view their appointments
@app.route("/api/appointments", methods=["GET"])
@jwt_required()
def get_appointments():
    try:
        user_id = int(get_jwt_identity())
        
        # Query appointments joining with User table to get doctor's name
        appointments = db.session.query(
            Appointment.id,
            Appointment.appointment_datetime,
            Appointment.reason,
            Appointment.status,
            User.full_name.label('doctor_name')
        ).join(
            User, Appointment.doctor_id == User.id # Join condition
        ).filter(
            Appointment.patient_id == user_id # Filter for the logged-in patient
        ).order_by(
            Appointment.appointment_datetime.desc() # Show most recent first
        ).all()

        appointment_list = [
            {
                'id': appt.id,
                'doctor_name': appt.doctor_name,
                'datetime': appt.appointment_datetime.strftime("%Y-%m-%d %I:%M %p"), # Format like: 2025-10-26 03:30 PM
                'reason': appt.reason,
                'status': appt.status
            } for appt in appointments
        ]
        
        return jsonify(appointment_list), 200

    except Exception as e:
        print(f"Get Appointments Error: {e}")
        return jsonify({'error': str(e)}), 500
    
# --- DOCTOR: GET all appointments assigned to this doctor ---
@app.route("/api/doctor/appointments", methods=["GET"])
@jwt_required()
def get_doctor_appointments():
    try:
        doctor_id = int(get_jwt_identity())
        
        # Security check: ensure the user is a doctor
        user = User.query.filter_by(id=doctor_id, role='doctor').first()
        if not user:
            return jsonify({'error': 'Access forbidden: Not a doctor'}), 403

        # Query appointments, joining with User to get patient's name
        appointments = db.session.query(
            Appointment.id,
            Appointment.appointment_datetime,
            Appointment.reason,
            Appointment.status,
            User.full_name.label('patient_name')
        ).join(
            User, Appointment.patient_id == User.id # Join on patient's ID
        ).filter(
            Appointment.doctor_id == doctor_id # Filter for this doctor
        ).order_by(
            Appointment.appointment_datetime.asc() # Show oldest first
        ).all()

        appointment_list = [
            {
                'id': appt.id,
                'patient_name': appt.patient_name,
                'datetime': appt.appointment_datetime.strftime("%Y-%m-%d %I:%M %p"),
                'reason': appt.reason,
                'status': appt.status
            } for appt in appointments
        ]
        
        return jsonify(appointment_list), 200

    except Exception as e:
        print(f"Get Doctor Appointments Error: {e}")
        return jsonify({'error': str(e)}), 500

# --- DOCTOR: Update an appointment's status (Approve/Reject) ---
@app.route("/api/appointments/<int:appointment_id>", methods=["PUT"])
@jwt_required()
def update_appointment_status(appointment_id):
    try:
        doctor_id = int(get_jwt_identity())
        data = request.get_json()
        new_status = data.get('status') # Expecting "Approved" or "Rejected"

        if not new_status or new_status not in ['Approved', 'Rejected']:
            return jsonify({'error': 'Invalid status provided'}), 400

        # Find the appointment
        appointment = Appointment.query.get(appointment_id)
        if not appointment:
            return jsonify({'error': 'Appointment not found'}), 404
        
        # Security check: ensure this doctor is the one assigned to this appointment
        if appointment.doctor_id != doctor_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Update the status
        appointment.status = new_status
        db.session.commit()
        
        return jsonify({'message': f'Appointment {appointment_id} updated to {new_status}'}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Update Appointment Error: {e}")
        return jsonify({'error': str(e)}), 500
    
# --- DOCTOR: GET all patients ---
@app.route("/api/doctor/patients", methods=["GET"])
@jwt_required()
def get_all_patients():
    try:
        # Security check: ensure user is a doctor
        doctor_id = int(get_jwt_identity())
        user = User.query.filter_by(id=doctor_id, role='doctor').first()
        if not user:
            return jsonify({'error': 'Access forbidden'}), 403

        # Query all patients and their details
        patients = db.session.query(
            User.id,
            User.full_name,
            Patient.age,
            Patient.gender,
            Patient.phone
        ).join(
            Patient, User.id == Patient.user_id
        ).filter(
            User.role == 'patient'
        ).order_by(
            User.full_name
        ).all()

        patient_list = [
            {
                'id': p.id,
                'full_name': p.full_name,
                'age': p.age,
                'gender': p.gender,
                'phone': p.phone
            } for p in patients
        ]
        
        return jsonify(patient_list), 200

    except Exception as e:
        print(f"Get All Patients Error: {e}")
        return jsonify({'error': str(e)}), 500

# --- DOCTOR: GET prediction history for a specific patient ---
@app.route("/api/doctor/patient_history/<int:patient_id>", methods=["GET"])
@jwt_required()
def get_patient_history_for_doctor(patient_id):
    try:
        # Security check: ensure user is a doctor
        doctor_id = int(get_jwt_identity())
        user = User.query.filter_by(id=doctor_id, role='doctor').first()
        if not user:
            return jsonify({'error': 'Access forbidden'}), 403
        
        # Check if patient exists
        patient = User.query.filter_by(id=patient_id, role='patient').first()
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        # Query predictions for this specific patient
        predictions = Prediction.query.filter_by(user_id=patient_id).order_by(Prediction.timestamp.desc()).all()
        history_list = [
            {
                'id': p.id,
                'result': p.result,
                'probability': f"{p.probability * 100:.2f}%",
                'timestamp': p.timestamp.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime("%Y-%m-%d %I:%M %p")
            } for p in predictions
        ]
        
        return jsonify(history_list), 200

    except Exception as e:
        print(f"Get Patient History Error: {e}")
        return jsonify({'error': str(e)}), 500

# --- DOCTOR: GET full details of a single prediction ---
@app.route("/api/doctor/prediction_details/<int:prediction_id>", methods=["GET"])
@jwt_required()
def get_prediction_details(prediction_id):
    try:
        # Security check: ensure user is a doctor
        doctor_id = int(get_jwt_identity())
        user = User.query.filter_by(id=doctor_id, role='doctor').first()
        if not user:
            return jsonify({'error': 'Access forbidden'}), 403

        # Find the prediction
        prediction = Prediction.query.get(prediction_id)
        if not prediction:
            return jsonify({'error': 'Prediction not found'}), 404
        
        # NOTE: This is a basic check. A more secure app would also verify
        # that this doctor is somehow linked to this patient.
        
        return jsonify({
            'id': prediction.id,
            'timestamp': prediction.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            'result': prediction.result,
            'probability': f"{prediction.probability * 100:.2f}%",
            'inputs': json.loads(prediction.input_data), # Send all the raw inputs
            'doctor_note': prediction.doctor_note or ''
            
        }), 200

    except Exception as e:
        print(f"Get Prediction Details Error: {e}")
        return jsonify({'error': str(e)}), 500

# --- DOCTOR: Add/Update a note on a prediction ---
@app.route("/api/doctor/prediction_note/<int:prediction_id>", methods=["PUT"])
@jwt_required()
def add_doctor_note(prediction_id):
    try:
        # Security check: ensure user is a doctor
        doctor_id = int(get_jwt_identity())
        user = User.query.filter_by(id=doctor_id, role='doctor').first()
        if not user:
            return jsonify({'error': 'Access forbidden'}), 403

        # Find the prediction
        prediction = Prediction.query.get(prediction_id)
        if not prediction:
            return jsonify({'error': 'Prediction not found'}), 404
        
        # Get the note from the request
        data = request.get_json()
        note = data.get('note')

        # Update and save the note
        prediction.doctor_note = note
        db.session.commit()
        
        return jsonify({'message': 'Note saved successfully'}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Save Note Error: {e}")
        return jsonify({'error': str(e)}), 500
    
# --- DOCTOR: GET all predictions that have a doctor's note ---
@app.route("/api/doctor/recommendations", methods=["GET"])
@jwt_required()
def get_all_recommendations():
    try:
        # Security check: ensure user is a doctor
        doctor_id = int(get_jwt_identity())
        user = User.query.filter_by(id=doctor_id, role='doctor').first()
        if not user:
            return jsonify({'error': 'Access forbidden'}), 403

        # Query all predictions that have a non-empty doctor_note
        # and join with User to get the patient's name
        notes = db.session.query(
            Prediction.id,
            Prediction.timestamp,
            Prediction.result,
            Prediction.doctor_note,
            User.id.label('patient_id'),
            User.full_name.label('patient_name')
        ).join(
            User, Prediction.user_id == User.id
        ).filter(
            Prediction.doctor_note.isnot(None),
            Prediction.doctor_note != ''
        ).order_by(
            Prediction.timestamp.desc()
        ).all()

        recommendations_list = [
            {
                'prediction_id': note.id,
                'patient_id': note.patient_id,
                'patient_name': note.patient_name,
                'timestamp': note.timestamp.strftime("%Y-%m-%d"),
                'result': note.result,
                'note': note.doctor_note
            } for note in notes
        ]
        
        return jsonify(recommendations_list), 200

    except Exception as e:
        print(f"Get All Recommendations Error: {e}")
        return jsonify({'error': str(e)}), 500
    
# --- 7. RUN THE FLASK APP & DB SETUP COMMAND ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # This will create the new Appointment table if it doesn't exist
        print("Database tables created (if they didn't exist).")
    app.run(debug=True, host='0.0.0.0', port=5000)

