import os
import pandas as pd
import pickle
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, classification_report

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data/raw/outcome_based_safety_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models/saved/outcome_safety_classifier.pkl")
GRAPHS_DIR = os.path.join(BASE_DIR, "data/evaluation_results/graphs")
os.makedirs(GRAPHS_DIR, exist_ok=True)

def plot_safety_metrics():
    # 1. Load Data and Model
    df = pd.read_csv(DATA_PATH)
    feature_cols = ["target_queue_length", "conflicting_volume", "time_since_last_phase", 
                    "num_conflicting_lanes", "downstream_lane_length", "clearance_distance"]
    X = df[feature_cols]
    y = df["label"]
    
    with open(MODEL_PATH, "rb") as f:
        clf = pickle.load(f)

    # 2. Get Test Set Predictions
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    y_pred = clf.predict(X_test)

    # 3. Print Report
    print("Classification Report (Copy this for your Thesis!):")
    print(classification_report(y_test, y_pred, target_names=["SAFE (0)", "UNSAFE (1)"]))

    # 4. Draw Heatmap
    cm = confusion_matrix(y_test, y_pred)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=["Predicted SAFE", "Predicted UNSAFE"],
                yticklabels=["Actual SAFE", "Actual UNSAFE"],
                annot_kws={"size": 16})
    
    plt.title("Safety Guard AI: Confusion Matrix", fontsize=16)
    plt.tight_layout()
    
    save_path = os.path.join(GRAPHS_DIR, "safety_confusion_matrix.png")
    plt.savefig(save_path, dpi=300)
    print(f"\nSaved Confusion Matrix graph to: {save_path}")

if __name__ == "__main__":
    plot_safety_metrics()