# CardioPredict

CardioPredict is a web application that leverages machine learning to analyze key health indicators and predict the likelihood of heart disease. The application provides instant health insights, generates automated lifestyle recommendations, and allows patients to book consultations with healthcare professionals.

The project is hosted live on: **[yashrb.pythonanywhere.com]**

## 🌟 Key Features

The application features a robust Role-Based Access Control (RBAC) system utilizing JWT authentication:

*   **Patient Dashboard:**
    *   Submit 16 health and lifestyle metrics (e.g., BMI, Exercise, Smoking History) for instant heart disease risk prediction.
    *   View personal prediction history and probability scores.
    *   Receive automated, personalized health recommendations based on input data.
    *   Browse a directory of doctors and book medical appointments.
*   **Doctor Dashboard:**
    *   View a list of assigned patients and access their complete prediction history.
    *   Manage appointment requests (Approve/Reject).
    *   Add and edit secure medical notes on individual patient predictions.
*   **Admin Dashboard:**
    *   Complete oversight of user management (edit or delete Patients, Doctors, and Admins).
    *   View all platform appointments and system-wide predictions.

## 💻 Tech Stack

*   **Backend:** Python, Flask, Flask-RESTful APIs.
*   **Database:** SQLite using Flask-SQLAlchemy.
*   **Authentication:** Flask-Bcrypt for password hashing, Flask-JWT-Extended for secure session management.
*   **Machine Learning:** Scikit-Learn, XGBoost, Pandas, and Imbalanced-Learn (SMOTE). The predictive engine uses a weighted average ensemble of Logistic Regression (30%) and XGBoost (70%).
*   **Frontend:** HTML5, Vanilla JavaScript (Single Page Application routing), and Tailwind CSS.

## 🚀 Local Installation & Setup

Follow these steps to run the application locally on your machine.

**1. Clone the repository**
` ` `bash
git clone https://github.com/Yash-GhubAccount/HeartDiseasePredictionG.git
cd CardioPredict
` ` `

**2. Set up a virtual environment (Recommended)**
` ` `bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
` ` `

**3. Install dependencies**
` ` `bash
pip install -r requirements.txt
` ` `

**4. Train the Machine Learning Models**
Before starting the server, you must train the models and generate the threshold files. Ensure `CVD_cleaned.csv` is in your root directory, then run:
` ` `bash
python model_trainer.py
` ` `
*Note: This script applies SMOTE for class imbalance and exports `logreg_pipeline.pkl`, `xgb_pipeline.pkl`, and `best_thresholds.pkl` into the `models/` directory.*

**5. Initialize the Database and Run the App**
` ` `bash
python app.py
` ` `
The application will automatically create the `cardiocare.db` SQLite database if it does not exist. The server will start on `http://0.0.0.0:5000/`.

## 📁 Project Structure

*   `app.py`: Main Flask application, API routing, and ML model integration.
*   `admin_panel.py`: Flask Blueprint containing all administrator endpoints.
*   `models.py`: SQLAlchemy database schemas (User, Patient, Doctor, Prediction, Appointment, Recommendation).
*   `model_trainer.py`: Data preprocessing, model training, and threshold evaluation pipeline.
*   `decorators.py`: Custom JWT wrappers enforcing role-based endpoint protection.
*   `static/script.js`: Frontend logic for API fetching, DOM manipulation, and dynamic dashboard rendering.
*   `templates/index.html`: Main UI template styled with Tailwind CSS.
