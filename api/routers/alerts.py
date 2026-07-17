"""
Alerts Endpoint

What this does:
Provides a URL (/alerts) that returns the most recent security alerts
from Elasticsearch, combining Suricata alerts and our own Python/ML alerts.
"""

from fastapi import APIRouter
from elasticsearch import Elasticsearch

router = APIRouter()


@router.get("/alerts")
def get_alerts():
    es = Elasticsearch("http://localhost:9200")

    suricata_query = {
        "size": 50,
        "sort": [{"@timestamp": "desc"}],
        "query": {
            "bool": {
                "must": [
                    {"range": {"@timestamp": {"gte": "now-24h"}}},
                    {"term": {"event_type": "alert"}}
                ]
            }
        }
    }
    suricata_response = es.search(index="nids-alerts-*", body=suricata_query)

    suricata_alerts = []
    for hit in suricata_response["hits"]["hits"]:
        data = hit["_source"]
        alert_info = data.get("alert")

        signature = None
        if alert_info is not None:
            signature = alert_info.get("signature")

        one_alert = {
            "source": "suricata",
            "timestamp": data.get("@timestamp"),
            "src_ip": data.get("src_ip"),
            "signature": signature
        }
        suricata_alerts.append(one_alert)

    python_query = {
        "size": 50
    }
    python_response = es.search(index="nids-python-alerts", body=python_query)

    python_alerts = []
    for hit in python_response["hits"]["hits"]:
        data = hit["_source"]

        one_alert = {
            "source": "python_detector",
            "detector": data.get("detector"),
            "src_ip": data.get("src_ip")
        }
        python_alerts.append(one_alert)

    return {
        "suricata_alerts": suricata_alerts,
        "python_alerts": python_alerts
    }
