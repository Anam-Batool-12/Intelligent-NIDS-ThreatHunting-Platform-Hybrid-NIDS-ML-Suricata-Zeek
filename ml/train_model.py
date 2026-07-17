"""
Train the Anomaly Detection Model

What this does:
1. Fetches recent connection data (as features) using features.py
2. Trains an Isolation Forest model on that data
3. Saves the trained model to a file, so predict.py can use it later

Run this once to create the model, and re-run it later if you want to
retrain on newer data.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from features import get_features

from sklearn.ensemble import IsolationForest
import joblib

print("Fetching training data...")
training_data = get_features(minutes_back=1440)

print("Got " + str(len(training_data)) + " connections to train on.")

if len(training_data) < 20:
    print("Not enough data to train a good model. Need at least 20 connections.")
    print("Let more traffic happen (or run a scan) and try again.")
    sys.exit(1)

model = IsolationForest(contamination=0.05, random_state=42)
model.fit(training_data)

print("Model trained successfully.")

model_path = os.path.join(os.path.dirname(__file__), "models", "isolation_forest.joblib")
joblib.dump(model, model_path)

print("Model saved to: " + model_path)
