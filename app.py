import flask
from flask import request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, JWTManager
import joblib
import pandas as pd
import os
import json 
from datetime import datetime

# --- 1. INITIALIZE FLASK APP & EXTENSIONS ---
app = flask.Flask(__name__)
CORS(app) 

# --- App Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'cardiocare.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["JWT_SECRET_KEY"] = "your-super-secret-key-change-me" 

# --- Initialize Extensions ---
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# --- 2. DEFINE DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient_details = db.relationship('Patient', backref='user', uselist=False, cascade="all, delete-orphan")
    doctor_details = db.relationship('Doctor', backref='user', uselist=False, cascade="all, delete-orphan")
    predictions = db.relationship('Prediction', backref='user', lazy=True, cascade="all, delete-orphan")

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
    result = db.Column(db.String(10), nullable=False)
    probability = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    input_data = db.Column(db.Text, nullable=False)


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
    email = data.get('email')
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already registered"}), 409
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    new_user = User(full_name=data['full_name'], email=email, password_hash=hashed_password, role=data['role'])
    db.session.add(new_user)
    db.session.commit()
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
    email = data.get('email')
    password = data.get('password')
    user = User.query.filter_by(email=email).first()
    if user and bcrypt.check_password_hash(user.password_hash, password):
        # Correctly cast the user ID to a string for the JWT identity.
        access_token = create_access_token(identity=str(user.id))
        return jsonify(access_token=access_token, userRole=user.role), 200
    return jsonify({"message": "Invalid credentials"}), 401

# --- 5. PREDICTION & HISTORY API ENDPOINTS ---
def generate_recommendations(user_inputs, prediction_result):
    recommendations = []
    if prediction_result == "Yes":
        recommendations.append("It is highly recommended to consult a healthcare professional to discuss these results.")
    else:
        recommendations.append("Continue to maintain a healthy lifestyle and schedule regular checkups with your doctor.")
    if user_inputs.get('Smoking_History') == 'Yes':
        recommendations.append("Quitting smoking is one of the most impactful steps you can take to improve cardiovascular health.")
    if float(user_inputs.get('BMI', 0)) >= 25.0:
        recommendations.append("Aiming for a BMI below 25 can significantly reduce heart disease risk.")
    return recommendations

@app.route("/api/predict", methods=["POST"])
@jwt_required()
def predict():
    if not all([lr_pipeline, xgb_pipeline, thresholds]):
        return jsonify({"error": "ML models are not loaded. Server setup is incomplete."}), 500
    try:
        user_id = int(get_jwt_identity())
        
        json_data = request.get_json()

        # FIX: Manually map binary string features to integers before prediction.
        binary_map = {"Yes": 1, "No": 0, "Male": 1, "Female": 0}
        binary_cols = [
            "Exercise", "Smoking_History", "Diabetes", "Depression",
            "Arthritis", "Skin_Cancer", "Other_Cancer", "Sex"
        ]
        for col in binary_cols:
            if col in json_data and isinstance(json_data[col], str):
                json_data[col] = binary_map.get(json_data[col])

        input_df = pd.DataFrame([json_data])
        
        probs_lr = lr_pipeline.predict_proba(input_df)[:, 1]
        probs_xgb = xgb_pipeline.predict_proba(input_df)[:, 1]
        weighted_avg_prob = (0.3 * probs_lr) + (0.7 * probs_xgb)
        threshold = thresholds['weighted_average']
        prediction_value = (weighted_avg_prob >= threshold).astype(int)[0]
        prediction_result = "Yes" if prediction_value == 1 else "No"
        probability_score = weighted_avg_prob[0]
        
        # Pass the original string data to recommendations, not the mapped data
        recommendation_list = generate_recommendations(request.get_json(), prediction_result)

        new_prediction = Prediction(result=prediction_result, probability=probability_score, user_id=user_id, input_data=str(request.get_json()))
        db.session.add(new_prediction)
        db.session.commit()

        response = {
            'prediction': prediction_result,
            'probability': f"{probability_score * 100:.2f}%",
            'recommendations': recommendation_list
        }
        return jsonify(response)
    except Exception as e:
        # Provide a more informative error message for debugging
        print(f"Prediction Error: {e}")
        return jsonify({'error': f"An error occurred during prediction: {e}"}), 400

@app.route("/api/history", methods=["GET"])
@jwt_required()
def get_history():
    try:
        user_id = int(get_jwt_identity())
        predictions = Prediction.query.filter_by(user_id=user_id).order_by(Prediction.timestamp.desc()).all()
        history_list = []
        for p in predictions:
            history_list.append({
                'id': p.id,
                'result': p.result,
                'probability': f"{p.probability * 100:.2f}%",
                'timestamp': p.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            })
        return jsonify(history_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- 6. RUN THE FLASK APP & DB SETUP COMMAND ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database tables created (if they didn't exist).")
    app.run(debug=True, host='0.0.0.0', port=5000)

