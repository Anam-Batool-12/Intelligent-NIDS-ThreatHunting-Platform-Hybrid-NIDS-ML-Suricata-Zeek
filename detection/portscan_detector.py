# Simple Slow Port Scan Detector
#

from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

query = {
    "size": 1000,
    "query": {
        "range": {
            "@timestamp": {
                "gte": "now-5m"
            }
        }
    }
}

response = es.search(index="nids-conn-*", body=query)

ip_to_ports = {}

for hit in response["hits"]["hits"]:
    data = hit["_source"]
    src_ip = data.get("id.orig_h")
    dest_port = data.get("id.resp_p")

    if src_ip is None or dest_port is None:
        continue

    if src_ip not in ip_to_ports:
        ip_to_ports[src_ip] = []

    if dest_port not in ip_to_ports[src_ip]:
        ip_to_ports[src_ip].append(dest_port)

THRESHOLD = 15

for ip in ip_to_ports:
    port_count = len(ip_to_ports[ip])

    if port_count >= THRESHOLD:
        print("ALERT: " + ip + " ne " + str(port_count) + " alag ports try kiye!")

        alert = {
            "detector": "slow_portscan",
            "src_ip": ip,
            "port_count": port_count
        }
        es.index(index="nids-python-alerts", document=alert)

print("Scan complete.")
