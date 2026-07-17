"""
Predict Anomalies Using the Trained Model

What this does:
1. Loads the trained model (saved earlier by train_model.py)
2. Fetches recent connections (last 5 minutes)
3. Asks the model: does this look normal or anomalous?
4. For anything flagged as anomalous, saves an alert to Elasticsearch

Run this periodically (e.g., every 5 minutes) after the model has been trained.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from features import get_features

import joblib
from elasticsearch import Elasticsearch

model_path = os.path.join(os.path.dirname(__file__), "models", "isolation_forest.joblib")

if not os.path.exists(model_path):
    print("No trained model found. Run train_model.py first.")
    sys.exit(1)

model = joblib.load(model_path)

print("Fetching recent connections...")
recent_data = get_features(minutes_back=5)

print("Got " + str(len(recent_data)) + " recent connections to check.")

if len(recent_data) == 0:
    print("No recent connections to check.")
    sys.exit(0)

predictions = model.predict(recent_data)

es = Elasticsearch("http://localhost:9200")

anomaly_count = 0

for i in range(len(recent_data)):
    if predictions[i] == -1:
        anomaly_count = anomaly_count + 1
        connection = recent_data[i]

        print("ANOMALY DETECTED: duration=" + str(connection[0]) +
              " orig_bytes=" + str(connection[1]) +
              " resp_bytes=" + str(connection[2]) +
              " orig_pkts=" + str(connection[3]))

        alert = {
            "detector": "ml_anomaly",
            "duration": connection[0],
            "orig_bytes": connection[1],
            "resp_bytes": connection[2],
            "orig_pkts": connection[3]
        }
        es.index(index="nids-python-alerts", document=alert)

print("Scan complete. Found " + str(anomaly_count) + " anomalies out of " + str(len(recent_data)) + " connections.")
