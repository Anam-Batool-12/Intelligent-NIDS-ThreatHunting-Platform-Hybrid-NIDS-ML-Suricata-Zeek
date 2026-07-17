"""
Feature Extractor for ML Anomaly Detection

What this does:
1. Fetches Zeek connection data from Elasticsearch
2. Extracts 4 numbers from each connection: duration, orig_bytes, resp_bytes, orig_pkts
3. Returns these numbers as a list, so they can be used for training or prediction

This file does nothing on its own - it is used by both train_model.py and predict.py.
"""

from elasticsearch import Elasticsearch


def get_features(minutes_back):
    """
    Fetches the last N minutes of connection data from Elasticsearch,
    and converts each connection into a [duration, orig_bytes, resp_bytes, orig_pkts] list.
    """
    es = Elasticsearch("http://localhost:9200")

    query = {
        "size": 5000,
        "query": {
            "range": {
                "@timestamp": {
                    "gte": "now-" + str(minutes_back) + "m"
                }
            }
        }
    }

    response = es.search(index="nids-conn-*", body=query)

    all_features = []

    for hit in response["hits"]["hits"]:
        data = hit["_source"]

        duration = data.get("duration")
        orig_bytes = data.get("orig_bytes")
        resp_bytes = data.get("resp_bytes")
        orig_pkts = data.get("orig_pkts")

        if duration is None or orig_bytes is None or resp_bytes is None or orig_pkts is None:
            continue

        try:
            duration = float(duration)
            orig_bytes = float(orig_bytes)
            resp_bytes = float(resp_bytes)
            orig_pkts = float(orig_pkts)
        except ValueError:
            continue

        one_connection = [duration, orig_bytes, resp_bytes, orig_pkts]
        all_features.append(one_connection)

    return all_features
