"""
Shared Elasticsearch client helper for all Python detection modules.

Reads connection settings from environment variables (see .env.example):
    ES_HOST                - e.g. http://localhost:9200
    ES_INDEX_CONN           - Zeek connection log index pattern prefix
    ES_INDEX_ALERTS         - Suricata alert index pattern prefix
"""

import os
from elasticsearch import Elasticsearch

ES_HOST = os.environ.get("ES_HOST", "http://localhost:9200")
ES_INDEX_CONN_PREFIX = os.environ.get("ES_INDEX_CONN", "nids-conn")
ES_INDEX_ALERTS_PREFIX = os.environ.get("ES_INDEX_ALERTS", "nids-alerts")

# Index where this project's own Python-based detectors write their findings.
# Kept separate from Suricata's index so we can always tell which engine
# generated which alert (useful for the paper's evaluation section).
PYTHON_ALERTS_INDEX = "nids-python-alerts"


def get_client() -> Elasticsearch:
    """Return a configured Elasticsearch client."""
    return Elasticsearch(ES_HOST)


def conn_index_pattern() -> str:
    return f"{ES_INDEX_CONN_PREFIX}-*"


def alerts_index_pattern() -> str:
    return f"{ES_INDEX_ALERTS_PREFIX}-*"
