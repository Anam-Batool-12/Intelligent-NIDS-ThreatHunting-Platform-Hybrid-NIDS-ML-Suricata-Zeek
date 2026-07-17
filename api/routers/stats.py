"""
Stats Endpoint

What this does:
Provides a URL (/stats) that returns summary numbers - total alerts,
how many from Suricata, how many from Python detectors, how many
from each detector type.
"""

from fastapi import APIRouter
from elasticsearch import Elasticsearch

router = APIRouter()


@router.get("/stats")
def get_stats():
    es = Elasticsearch("http://localhost:9200")

    suricata_count_query = {
        "query": {
            "range": {
                "@timestamp": {"gte": "now-24h"}
            }
        }
    }
    suricata_result = es.count(index="nids-alerts-*", body=suricata_count_query)
    suricata_total = suricata_result["count"]

    python_result = es.count(index="nids-python-alerts")
    python_total = python_result["count"]

    detector_query = {
        "size": 0,
        "aggs": {
            "by_detector": {
                "terms": {
                    "field": "detector.keyword"
                }
            }
        }
    }
    detector_response = es.search(index="nids-python-alerts", body=detector_query)

    detector_breakdown = {}
    for bucket in detector_response["aggregations"]["by_detector"]["buckets"]:
        detector_name = bucket["key"]
        count = bucket["doc_count"]
        detector_breakdown[detector_name] = count

    return {
        "suricata_alerts_24h": suricata_total,
        "python_ml_alerts_total": python_total,
        "breakdown_by_detector": detector_breakdown
    }
