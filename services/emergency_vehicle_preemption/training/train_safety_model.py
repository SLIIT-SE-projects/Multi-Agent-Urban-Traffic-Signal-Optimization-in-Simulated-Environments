import pandas as pd
import pickle
import os
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import classification_report, confusion_matrix

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "../data/raw/outcome_based_safety_data.csv")
MODEL_DIR = os.path.join(BASE_DIR, "../models/saved")
os.makedirs(MODEL_DIR, exist_ok=True)

def train_safety_model():
    print("--- 1. LOADING DATA ---")
    if not os.path.exists(DATA_PATH):
        print(f"CRITICAL ERROR: Data file not found at {DATA_PATH}.")
        print("Please run 'outcome_based_data_generator.py' first.")
        return

    df = pd.read_csv(DATA_PATH)
    
    # Define our 6 Context-Aware Features
    feature_cols = [
        "target_queue_length", 
        "conflicting_volume", 
        "time_since_last_phase", 
        "num_conflicting_lanes", 
        "downstream_lane_length", 
        "clearance_distance"
    ]
    
    X = df[feature_cols]
    y = df["label"]

    print(f"Loaded {len(df)} simulated intersection snapshots.")
    print("Class Distribution:")
    print(y.value_counts().rename(index={0: '🟢 SAFE (0)', 1: '🔴 UNSAFE (1)'}))

    # --- 2. TRAIN / TEST SPLIT ---
    # Stratify=y ensures the 80/20 split maintains the same Safe/Unsafe ratio
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("\n--- 2. TRAINING DECISION TREE ---")
    # We use class_weight="balanced" because UNSAFE scenarios might be rare.
    # This heavily penalizes the model if it misses an UNSAFE situation (False Negative).
    # We restrict max_depth to prevent overfitting and keep the rules interpretable.
    clf = DecisionTreeClassifier(
        max_depth=5, 
        min_samples_leaf=10, 
        class_weight="balanced", 
        random_state=42
    )
    
    clf.fit(X_train, y_train)
    print("Training complete.")

    # --- 3. EVALUATION ---
    print("\n--- 3. MODEL EVALUATION ---")
    y_pred = clf.predict(X_test)
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["SAFE (0)", "UNSAFE (1)"]))
    
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"True SAFE (Predicted Safe): {cm[0][0]}")
    print(f"False UNSAFE (Predicted Unsafe, but was Safe): {cm[0][1]} <- (Acceptable caution)")
    print(f"False SAFE (Predicted Safe, but was UNSAFE): {cm[1][0]} <- (CRITICAL ERROR)")
    print(f"True UNSAFE (Predicted Unsafe): {cm[1][1]}")

    # --- 4. INTERPRETABILITY (THE "AI RULES") ---
    print("\n--- 4. EXTRACTED PHYSICS RULES ---")
    print("Here is a sample of the rules the AI discovered from the simulation:")
    tree_rules = export_text(clf, feature_names=feature_cols, max_depth=3)
    print(tree_rules)

    # --- 5. SAVE MODEL ---
    save_path = os.path.join(MODEL_DIR, "outcome_safety_classifier.pkl")
    with open(save_path, "wb") as f:
        pickle.dump(clf, f)
    
    print(f"\nSUCCESS: Safety Classifier saved to {save_path}")

if __name__ == "__main__":
    train_safety_model()