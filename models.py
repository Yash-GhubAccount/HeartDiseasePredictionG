# models.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()


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
    # Relationships for appointments
    patient_appointments = db.relationship('Appointment', foreign_keys='Appointment.patient_id', backref='patient', lazy=True, cascade="all, delete-orphan")
    doctor_appointments = db.relationship('Appointment', foreign_keys='Appointment.doctor_id', backref='doctor', lazy=True, cascade="all, delete-orphan")

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    specialization = db.Column(db.String(100))
    experience_years = db.Column(db.Integer)
    clinic_address = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    result = db.Column(db.String(10), nullable=False)
    probability = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    input_data = db.Column(db.Text, nullable=False)
    doctor_note = db.Column(db.Text)
    recommendations = db.relationship('Recommendation', backref='prediction', lazy=True, cascade="all, delete-orphan")

class Recommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    prediction_id = db.Column(db.Integer, db.ForeignKey('prediction.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appointment_datetime = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
