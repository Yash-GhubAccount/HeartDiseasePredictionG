import os
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier
from sklearn.metrics import (
    roc_auc_score, accuracy_score, precision_score, 
    recall_score, f1_score, classification_report,
    precision_recall_curve
)
from sklearn.compose import ColumnTransformer
# We use the pipeline from imblearn to properly integrate SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline 
from imblearn.over_sampling import SMOTE 
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')
warnings.filterwarnings('ignore', category=FutureWarning)


# ──────────────────────────────
# 1. Load Dataset
# ──────────────────────────────
DATASET_FILENAME = "CVD_cleaned.csv"
try:
    df = pd.read_csv(DATASET_FILENAME)
    print("Dataset loaded successfully.")
except FileNotFoundError:
    print(f"Error: '{DATASET_FILENAME}' not found.")
    print("Please download the dataset from the specified Kaggle link and place it in the same folder as this script.")
    exit()

features = [
    "General_Health","Checkup","Exercise","Smoking_History",
    "Alcohol_Consumption","Fruit_Consumption","Green_Vegetables_Consumption",
    "FriedPotato_Consumption","BMI","Sex","Age_Category","Diabetes",
    "Depression","Arthritis","Skin_Cancer","Other_Cancer"
]
target = "Heart_Disease"

X = df[features]
y = df[target].map({"Yes": 1, "No": 0})

# ──────────────────────────────
# 2. Define Preprocessing
# ──────────────────────────────
categorical_features = [
    "General_Health", "Checkup", "Exercise", "Smoking_History", 
    "Sex", "Age_Category", "Diabetes", "Depression", 
    "Arthritis", "Skin_Cancer", "Other_Cancer"
]
numerical_features = [
    "Alcohol_Consumption", "Fruit_Consumption", "Green_Vegetables_Consumption",
    "FriedPotato_Consumption", "BMI"
]

preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), numerical_features),
        ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features)
    ],
    remainder='passthrough'
)
print("Preprocessor defined.")

# ──────────────────────────────
# 3. Split Data (BEFORE SMOTE)
# ──────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, 
    test_size=0.3,  
    random_state=42, 
    stratify=y       
)
print(f"Data split: {len(y_train)} train, {len(y_test)} test samples.")
print(f"Train set 'Yes' count: {y_train.sum()} ({y_train.mean()*100:.2f}%)")
print(f"Test set 'Yes' count:  {y_test.sum()} ({y_test.mean()*100:.2f}%)")

# ──────────────────────────────
# 4. Define and Train Models
# ──────────────────────────────

# --- Logistic Regression Pipeline with SMOTE ---
lr_pipeline = ImbPipeline([
    ('preprocessor', preprocessor),
    ('smote', SMOTE(random_state=42)), 
    ('model', LogisticRegression(
        solver='liblinear', 
        random_state=42
    ))
])

# --- XGBoost Pipeline with SMOTE ---
xgb_pipeline = ImbPipeline([
    ('preprocessor', preprocessor),
    ('smote', SMOTE(random_state=42)), 
    ('model', XGBClassifier(
        random_state=42, 
        use_label_encoder=False, 
        eval_metric='logloss'
    ))
])

# Train models
print("\nTraining Logistic Regression...")
lr_pipeline.fit(X_train, y_train)
print("Logistic Regression training complete.")

print("\nTraining XGBoost...")
xgb_pipeline.fit(X_train, y_train)
print("XGBoost training complete.")

# ──────────────────────────────
# 5. Evaluate Individual Models
# ──────────────────────────────

# Get probabilities from the test set
probs_lr = lr_pipeline.predict_proba(X_test)[:, 1]
probs_xgb = xgb_pipeline.predict_proba(X_test)[:, 1]

# Clean probabilities of any NaN/Inf values just in case
probs_lr = np.nan_to_num(probs_lr)
probs_xgb = np.nan_to_num(probs_xgb)

def evaluate_from_probs(model_name, y_true, y_probs, min_recall=0.75):
    """
    Finds the best threshold that achieves a minimum recall
    while maximizing precision.
    """
    print(f"\n--- Evaluating {model_name} ---")
    
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_probs)
    
    # We need to handle the last threshold, which is always 1.0
    # and has recall 0. We'll append it to make arrays match.
    if len(precisions) == len(thresholds):
        precisions = precisions[:-1]
        recalls = recalls[:-1]

    # Find all thresholds that meet our minimum recall requirement
    passing_threshold_indices = np.where(recalls >= min_recall)[0]
    
    if len(passing_threshold_indices) == 0:
        # If no threshold meets our recall, we have a problem.
        # Fall back to maximizing F1-score as a contingency.
        print(f"⚠️ WARNING: No threshold achieved {min_recall*100}% recall.")
        print("Falling back to optimizing for best F1-score.")
        f1_scores = (2 * precisions * recalls) / (precisions + recalls)
        f1_scores = np.nan_to_num(f1_scores)
        best_idx = np.argmax(f1_scores)
    else:
        # From the "safe" thresholds, find the one with the highest precision
        print(f"✅ Found {len(passing_threshold_indices)} thresholds with >= {min_recall*100}% recall.")
        precision_at_min_recall = precisions[passing_threshold_indices]
        best_idx = passing_threshold_indices[np.argmax(precision_at_min_recall)]

    best_threshold = thresholds[best_idx]
    
    # Get predictions based on this optimal threshold
    y_pred_optimal = (y_probs >= best_threshold).astype(int)
    
    print("\nClassification Report (with optimal threshold):")
    report = classification_report(y_true, y_pred_optimal, target_names=["No Heart Disease", "Heart Disease"])
    print(report)
    
    auc_score = roc_auc_score(y_true, y_probs)
    print(f"AUC Score = {auc_score:.4f}")
    
    # Return the threshold
    return best_threshold

# Run evaluations
best_threshold_lr = evaluate_from_probs("Logistic Regression", y_test, probs_lr)
best_threshold_xgb = evaluate_from_probs("XGBoost", y_test, probs_xgb)

# ──────────────────────────────
# 6. Ensemble Evaluation
# ──────────────────────────────
# Simple Average Ensemble
simple_avg_probs = (probs_lr + probs_xgb) / 2
best_threshold_simple_avg = evaluate_from_probs("Simple Average Ensemble", y_test, simple_avg_probs)

# Weighted Average Ensemble (30% LR, 70% XGB)
weighted_avg_probs = (0.3 * probs_lr) + (0.7 * probs_xgb)
best_threshold_weighted_avg = evaluate_from_probs("Weighted Average Ensemble (30% LR, 70% XGB)", y_test, weighted_avg_probs)


# ──────────────────────────────
# 7. Save Models & Thresholds
# ──────────────────────────────
output_dir = "models_latestv2"
os.makedirs(output_dir, exist_ok=True)

# Save the entire pipeline (preprocessor + smote + model)
joblib.dump(lr_pipeline, os.path.join(output_dir, "logreg_pipeline.pkl"))
joblib.dump(xgb_pipeline, os.path.join(output_dir, "xgb_pipeline.pkl"))

# Save the best thresholds for all strategies in a dictionary
thresholds = {
    "logistic_regression": best_threshold_lr,
    "xgboost": best_threshold_xgb,
    "simple_average": best_threshold_simple_avg,
    "weighted_average": best_threshold_weighted_avg
}
joblib.dump(thresholds, os.path.join(output_dir, "best_thresholds.pkl"))

print(f"\n✅ Models and all thresholds saved to the '{output_dir}' directory!")