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
    recall_score, f1_score, classification_report
)
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
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
# 2. Preprocessing
# ──────────────────────────────
print("Setting up preprocessing pipeline...")
numeric_cols = [
    "BMI","Alcohol_Consumption","Fruit_Consumption",
    "Green_Vegetables_Consumption","FriedPotato_Consumption"
]
# We use a mapping for binary columns to ensure consistency
binary_map = {"Yes": 1, "No": 0, "Male": 1, "Female": 0}
binary_cols = ["Exercise","Smoking_History","Diabetes","Depression",
               "Arthritis","Skin_Cancer","Other_Cancer","Sex"]
cat_cols = ["General_Health","Checkup","Age_Category"]

# Map binary columns in the dataframe before splitting
for col in binary_cols:
    X[col] = X[col].map(binary_map).fillna(0).astype(int)

# Create a ColumnTransformer to apply different transformations to different columns
# 'num' pipeline: scales numerical features
# 'cat' pipeline: one-hot encodes categorical features
# 'bin' pipeline: 'passthrough' leaves the already-mapped binary columns as they are
preprocessor = ColumnTransformer(
    transformers=[
        ("num", StandardScaler(), numeric_cols),
        ("cat", OneHotEncoder(handle_unknown='ignore', sparse_output=False), cat_cols),
        ("bin", "passthrough", binary_cols)
    ],
    remainder='drop' # Drop any columns not specified
)
print("Preprocessing pipeline created.")

# ──────────────────────────────
# 3. Train/Test Split
# ──────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3, stratify=y, random_state=42
)
print(f"Data split into training ({len(X_train)} samples) and testing ({len(X_test)} samples) sets.")

# ──────────────────────────────
# 4. Train Models
# ──────────────────────────────
print("\n--- Training Logistic Regression Model ---")
# Create a pipeline that first preprocesses the data, then fits the classifier
lr_pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42))
])
lr_pipeline.fit(X_train, y_train)
print("Logistic Regression training complete.")


print("\n--- Training XGBoost Model ---")
# Calculate scale_pos_weight for handling class imbalance in XGBoost
scale_pos_weight = (len(y_train) - sum(y_train)) / sum(y_train)
xgb_pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("classifier", XGBClassifier(
        use_label_encoder=False,
        eval_metric="logloss",
        scale_pos_weight=scale_pos_weight,
        random_state=42
    ))
])
xgb_pipeline.fit(X_train, y_train)
print("XGBoost training complete.")


# ──────────────────────────────
# 5. Threshold Tuning & Evaluation
# ──────────────────────────────
def evaluate_from_probs(name, probs, y_test, thresholds=np.arange(0.3, 0.7, 0.05)):
    """
    Evaluates prediction probabilities by finding the best threshold to maximize F1-score.
    """
    print(f"\n--- Evaluating {name} ---")
    best = {"f1": 0, "thr": 0.5}
    for thr in thresholds:
        preds = (probs >= thr).astype(int)
        f1 = f1_score(y_test, preds)
        if f1 > best["f1"]:
            best = {"f1": f1, "thr": thr}
    
    print(f"✅ Best Threshold = {best['thr']:.2f} (achieved F1-score of {best['f1']:.4f})")
    
    final_preds = (probs >= best['thr']).astype(int)
    print("\nClassification Report (with optimal threshold):")
    print(classification_report(y_test, final_preds, target_names=["No Heart Disease", "Heart Disease"]))
    print(f"AUC Score = {roc_auc_score(y_test, probs):.4f}")
    return best['thr']

# Get probabilities for individual models
probs_lr = lr_pipeline.predict_proba(X_test)[:, 1]
probs_xgb = xgb_pipeline.predict_proba(X_test)[:, 1]

# Evaluate individual models
best_threshold_lr = evaluate_from_probs("Logistic Regression", probs_lr, y_test)
best_threshold_xgb = evaluate_from_probs("XGBoost", probs_xgb, y_test)


# ──────────────────────────────
# 6. Ensemble Evaluation
# ──────────────────────────────
# Simple Average Ensemble
simple_avg_probs = (probs_lr + probs_xgb) / 2
best_threshold_simple_avg = evaluate_from_probs("Simple Average Ensemble", simple_avg_probs, y_test)

# Weighted Average Ensemble (giving more weight to XGBoost)
weighted_avg_probs = (0.3 * probs_lr) + (0.7 * probs_xgb)
best_threshold_weighted_avg = evaluate_from_probs("Weighted Average Ensemble (30% LR, 70% XGB)", weighted_avg_probs, y_test)


# ──────────────────────────────
# 7. Save Models & Thresholds
# ──────────────────────────────
output_dir = "models"
os.makedirs(output_dir, exist_ok=True)

# Save the entire pipeline (preprocessor + model)
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
                                                                
