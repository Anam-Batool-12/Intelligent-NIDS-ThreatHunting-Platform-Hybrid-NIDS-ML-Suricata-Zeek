"""
Timeline Endpoint

What this does:
Provides a URL (/timeline) that groups alerts by hour, so we can see
"how many alerts happened in each hour" - useful for a chart.
"""

from fastapi import APIRouter
from elasticsearch import Elasticsearch

router = APIRouter()


@router.get("/timeline")
def get_timeline():
    es = Elasticsearch("http://localhost:9200")

    query = {
        "size": 0,
        "query": {
            "range": {
                "@timestamp": {"gte": "now-24h"}
            }
        },
        "aggs": {
            "alerts_per_hour": {
                "date_histogram": {
                    "field": "@timestamp",
                    "calendar_interval": "hour"
                }
            }
        }
    }

    response = es.search(index="nids-alerts-*", body=query)

    buckets = response["aggregations"]["alerts_per_hour"]["buckets"]

    timeline_data = []
    for bucket in buckets:
        one_point = {
            "hour": bucket["key_as_string"],
            "alert_count": bucket["doc_count"]
        }
        timeline_data.append(one_point)

    return {"timeline": timeline_data}
