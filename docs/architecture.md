# Architecture

## Overview

This platform combines signature-based detection (Suricata), protocol-level
logging (Zeek), an ELK log pipeline, custom Python attack detectors, and a
machine learning anomaly detection layer into a single alerting system,
exposed via a FastAPI backend and Kibana dashboard.

```
Network Traffic
     |
     v
[Suricata] --eve.json-->  [Logstash] --> [Elasticsearch] --> [Kibana Dashboard]
[Zeek]     --conn/dns/http logs-->  |            ^
     |                              |            |
     v                              v            |
[Python Detectors]  <-------->  [ML Anomaly Engine]
     |                              |
     +------------> [nids-python-alerts index] ----> [FastAPI] --> /alerts /timeline /stats
```

## Lab Topology

| Host    | Hypervisor        | Role     | Network Mode | IP (example)      |
|---------|--------------------|----------|--------------|--------------------|
| Kali    | VMware Workstation | Sensor   | Bridged (`eth0`) | `192.168.100.x` |
| Debian  | VirtualBox         | Attacker | Bridged      | `192.168.100.x`   |

Both VMs are bridged to the physical WiFi network so traffic between them
traverses each host's monitored network interface - this is required for
Suricata/Zeek to actually observe the traffic. Same-host traffic (e.g., a
tool scanning `127.0.0.1` or its own primary IP) is routed via the kernel's
loopback shortcut and never reaches the af-packet capture point, so it will
not generate detections.

**Note on VMware + WiFi bridging:** by default VMware's bridged network
(`VMnet0`) is set to "Automatic," which can select the wrong or a
disconnected host adapter. If a bridged VM gets a `169.254.x.x`
(link-local/APIPA) address instead of a real DHCP lease, open
**Edit -> Virtual Network Editor -> VMnet0 -> Bridged to**, and manually select
the active WiFi adapter (or use "Automatic Settings" and only enable the
WiFi adapter).

## Component Status

| Component | Status | Notes |
|---|---|---|
| Suricata (signature detection) | Done | Custom ruleset loaded, live scan detection verified |
| Zeek (protocol logging) | Done | Deployed via zeekctl, custom DNS tunneling script active, scan detection verified in `conn.log` |
| Logstash to Elasticsearch pipeline | Done | Both Suricata `eve.json` and Zeek `conn.log` flowing into Elasticsearch |
| Kibana Dashboard | Done | Data views created (`nids-alerts`, `nids-conn`), verified searchable (51K+ alert docs, 270 custom-rule alerts) |
| Python detection modules | Done | 5 detectors implemented and tested: slow port scan, brute force, DoS, SQLi confirmation, DNS tunneling confirmation |
| ML anomaly detection | Done | Isolation Forest trained on Zeek connection features; verified flagging a live anomalous connection |
| FastAPI (alerts/timeline/stats) | Done | All three endpoints verified returning live data via `/docs` |
| Automatic scheduling (cron) | Done | All detectors, ML predictor, and Docker Compose run automatically |
| Threat intel enrichment | Future work | Not implemented in this version |
| Custom dashboard (beyond Kibana) | Skipped | Kibana + FastAPI JSON endpoints considered sufficient |
| CIC-IDS2017 benchmark evaluation | Future work | Planned for quantitative precision/recall/F1 evaluation |

## Suricata Setup (Completed)

### Configuration
- **Interface:** `eth0` (af-packet capture)
- **HOME_NET:** `192.168.0.0/16,10.0.0.0/8,172.16.0.0/12`
- **Rule path:** `/var/lib/suricata/rules/` (this is the `default-rule-path`
  resolved from `suricata.yaml` on this install - confirm with
  `grep default-rule-path /etc/suricata/suricata.yaml`, as it can vary by
  distro/package)
- **Custom rules file:** added as an entry under `rule-files:` in
  `suricata.yaml`, alongside the Emerging Threats `suricata.rules`

### Custom Ruleset
12 rules, SID range `9000001`-`9000041`, covering DoS/flood, port scan,
brute force, SQL injection, and DNS tunneling. Full source:
[`capture/suricata/rules/custom.rules`](../capture/suricata/rules/custom.rules).

### Verification
A live TCP SYN scan (`nmap -sS -Pn -p 1-100`) launched from the Debian
attacker host against the Kali sensor host triggered both Suricata's
built-in decoder-level scan detection (SID 3400002) and the project's
custom port-scan rule (SID 9000010), confirming the full pipeline - traffic
capture, rule matching, and alert logging - functions end-to-end.

Excerpt from `fast.log`:
```
07/08/2026-23:53:35.155629 [**] [1:9000010:1] CUSTOM Possible Port Scan
(many ports, single source) [**] [Classification: Detection of a Network
Scan] [Priority: 3] {TCP} 192.168.100.114:33066 -> 192.168.100.115:80
```

### Useful commands
```bash
# Test config for syntax errors without starting the daemon
sudo suricata -T -c /etc/suricata/suricata.yaml -v

# Restart after config/rule changes
sudo systemctl restart suricata
sudo systemctl enable suricata  # ensure it survives reboot

# Watch alerts live
sudo tail -f /var/log/suricata/fast.log
# Check interface capture stats
sudo suricatasc -c "iface-stat eth0"
```

## Zeek Setup (Completed)

### Installation
Kali's default `zeek` package (5.1.1) had broken dependencies against the
system's current `libc6`. Installed instead from the official Zeek OBS
repository (`security:zeek` Debian_Testing channel), which provided a
compatible build (8.2.1).

### Configuration
- Managed via `zeekctl` (install -> deploy workflow) rather than running
  `zeek` directly, so it persists as a standalone service.
- `local.zeek` extended with `@load ./scripts/dns_tunnel_detect.zeek` to
  load the project's custom DNS tunneling heuristics, and with Community ID
  logging enabled for later Suricata/Zeek alert correlation.
- **Auto-start on boot:** zeekctl does not register a systemd service by
  default; a cron `@reboot` entry (`sleep 30 && zeekctl deploy`) was added
  to ensure Zeek restarts after VM reboot, once the network interface is
  ready.

### Verification
A live TCP SYN scan produced a clear signature in `conn.log`: many
connections from the same source port to sequential destination ports, all
with `REJ` (rejected/closed port) connection state - confirming Zeek
captures the same attack Suricata alerts on, independently, at the
connection-log level (useful both for ML feature extraction and for
correlating with Suricata alerts via Community ID).

### Useful commands
```bash
sudo /opt/zeek/bin/zeekctl status
sudo /opt/zeek/bin/zeekctl deploy    # re-apply config after changes
sudo tail -f /opt/zeek/logs/current/conn.log
```

## ELK Stack Setup (Completed)

### Deployment
Elasticsearch, Logstash, and Kibana (all v8.14.0) are run via Docker
Compose. Logstash mounts the live Suricata and Zeek log directories
read-only and ships parsed events into two daily-rotated Elasticsearch
indices: `nids-alerts-*` (from Suricata `eve.json`) and `nids-conn-*`
(from Zeek `conn.log`).

### Issues encountered and fixes
1. **Wrong Docker socket (Podman conflict):** the `podman-docker` package
   sets `DOCKER_HOST` to Podman's socket by default, causing
   `docker compose` to fail with a misleading "no such file or directory"
   error. Fixed with `unset DOCKER_HOST` (added to both `.bashrc` and
   `.zshrc`, since the shell in use varied by session).
2. **Permission denied on Docker socket:** the user was not in the
   `docker` group. Fixed with `sudo usermod -aG docker $USER`.
3. **Wrong volume mount paths:** the initial `docker-compose.yml` mounted
   the project's local `capture/suricata` and `capture/zeek` config
   folders (which only contain configuration, not live logs) instead of
   the actual runtime log paths (`/var/log/suricata`,
   `/opt/zeek/logs/current`). Editing config files in place can silently
   leave duplicate/stale volume entries - always re-`grep` the compose file
   after edits and use `docker inspect <container> | grep -A3 Source` to
   confirm what's actually mounted, since `docker compose restart` does
   **not** pick up new volume definitions - `docker compose up -d
   --force-recreate <service>` is required.
4. **Zeek spool directory permissions:** `/opt/zeek/spool` was
   `drwxrws---` (no access for "others"), blocking the Logstash container's
   user from reading `conn.log` through the `current` symlink. Fixed with
   `chmod o+rx /opt/zeek/spool` (note: `chmod -R` on `/opt/zeek/logs`
   alone does not fix this, since `current` is a symlink to a different
   path entirely - use `namei -l <path>` to find exactly which directory
   in the chain is blocking access).

### Verification
Kibana Discover, querying the `nids-alerts` data view, showed 51,231 total
documents and 270 matching `alert.signature: "CUSTOM*"` (i.e., generated
by this project's own rules specifically, not the Emerging Threats
ruleset) - confirming the full pipeline from packet capture through to a
searchable dashboard.

### Useful commands
```bash
docker compose up -d elasticsearch logstash kibana
docker compose ps
docker compose logs logstash --tail 60
curl -s "http://localhost:9200/_cat/indices?v" | grep nids
```

## Python Detection Modules (Completed)

### Purpose
Suricata's custom rules use short (5-60 second) threshold windows to stay
fast and memory-efficient. An attacker who spreads an attack out over
several minutes can stay under those thresholds indefinitely. The Python
detection modules close this gap by querying data already stored in
Elasticsearch over longer windows, and by cross-referencing repeated
Suricata alerts to separate one-off false positives from confirmed,
repeated attack behavior.

### Design
All five detectors share the same simple structure (deliberately written
with basic loops and dictionaries rather than Elasticsearch aggregation
queries, so the logic is easy to read and explain):
1. Query Elasticsearch for recent records (either Zeek's `nids-conn-*` or
   Suricata's `nids-alerts-*`, depending on the detector).
2. Loop through results, building a Python dictionary that counts
   occurrences per source IP (or per IP+port).
3. Compare each count against a threshold constant.
4. If crossed, print an alert and write a new document into a dedicated
   `nids-python-alerts` Elasticsearch index (kept separate from Suricata's
   own alerts so the source of each detection is always traceable).

### The five detectors

| Detector | Data source | Logic |
|---|---|---|
| `portscan_detector.py` | `nids-conn-*` (Zeek) | Counts distinct destination ports touched by each source IP over a 5-minute window; flags 15+ |
| `bruteforce_detector.py` | `nids-conn-*` (Zeek) | Counts connection attempts to login ports (22/SSH, 21/FTP, 3389/RDP) per source IP over 5 minutes; flags 10+ |
| `dos_detector.py` | `nids-conn-*` (Zeek) | Counts total connections per source IP over a 2-minute window (short, since DoS is fast); flags 100+ |
| `sqli_detector.py` | `nids-alerts-*` (Suricata) | Counts how many times each source IP triggered a Suricata SQLi rule over 10 minutes; flags 3+ as "confirmed" rather than a one-off false positive |
| `dns_tunnel_detector.py` | `nids-alerts-*` (Suricata) | Same confirmation pattern as SQLi, applied to Suricata's DNS tunneling rules |

**Why SQLi and DNS tunneling detectors read from Suricata's alerts rather
than raw traffic:** Zeek's `conn.log` (the only Zeek log currently ingested
into Elasticsearch) contains connection metadata only - no HTTP URIs or DNS
query strings. Extending the pipeline to ingest `http.log` and `dns.log`
would allow payload-level Python detection for these two attack types; for
now, these two detectors add value by turning Suricata's single alerts into
a confidence-scored "this happened repeatedly" signal, which is itself a
common real-world SOC technique for reducing alert fatigue.

### Environment
Detectors run inside a Python virtual environment (`venv/`) with the
`elasticsearch==8.14.0` client pinned to match the deployed Elasticsearch
server version (the latest client on PyPI, v9.x, is not guaranteed
compatible with an 8.x server).

### Verification
All five scripts were run against live data and completed without errors
("Scan complete."). They now run automatically via cron (see below).

## ML Anomaly Detection (Completed)

### Design
An Isolation Forest model (`scikit-learn`) is trained on four numeric
features extracted from each Zeek connection record: `duration`,
`orig_bytes`, `resp_bytes`, `orig_pkts`. Isolation Forest is an
unsupervised algorithm - it is never told which connections are attacks;
it learns the statistical shape of "normal" from the training data, and
flags points that are easy to separate from the rest (few random splits
needed to isolate them) as anomalies.

- `ml/features.py` - fetches recent Zeek connection data from
  Elasticsearch and extracts the four numeric features per connection.
- `ml/train_model.py` - fetches a training window (24 hours), fits an
  `IsolationForest(contamination=0.05, random_state=42)`, and saves the
  trained model with `joblib`.
- `ml/predict.py` - loads the saved model, fetches recent (5-minute)
  connections, scores them, and writes an alert to `nids-python-alerts`
  for anything flagged as anomalous (`prediction == -1`).

### Verification and a known limitation
The model was trained on 79 connections and, in live testing, correctly
flagged a genuinely anomalous connection (28-second duration, 1958 bytes
sent, 0 bytes received - a one-directional, unusually long connection).

However, an earlier test run found the model did **not** flag a fresh port
scan as anomalous. This is because the 24-hour training window itself
included multiple manually-run port scans from earlier development
testing, so the model had already learned to treat scan-like traffic as
"normal" - a textbook case of training-data contamination in unsupervised
anomaly detection. This is documented as a known limitation; the fix is to
retrain on a verified clean traffic window, or periodically retrain with
review.

### Useful commands
```bash
source venv/bin/activate
python3 ml/train_model.py     # retrain the model
python3 ml/predict.py         # score recent connections
```

## FastAPI Backend (Completed)

### Design
A small FastAPI application (`api/main.py`) exposes three endpoints, each
querying Elasticsearch directly and returning JSON:

| Endpoint | Purpose |
|---|---|
| `/alerts` | Most recent Suricata alerts (`event_type: alert` filter applied) and Python/ML alerts, combined |
| `/timeline` | Alert counts bucketed by hour, for charting |
| `/stats` | Total counts and a breakdown by Python detector type |
| `/docs` | Auto-generated interactive API documentation (Swagger UI) |

### Issue encountered and fix
An early version of `/alerts` returned `null` for `src_ip` and
`signature` on most records. Root cause: `nids-alerts-*` contains every
Suricata event type (flow, dns, http, alert, etc.), and only records with
`event_type: "alert"` carry the `alert.signature` field. Fixed by adding
an explicit `{"term": {"event_type": "alert"}}` filter to the query.

### Useful commands
```bash
source venv/bin/activate
uvicorn api.main:app --reload --host 0.0.0.0
# then visit http://<host-ip>:8000/docs
```

## Automatic Scheduling (Completed)

All five Python detectors, the ML predictor, and the Docker-based ELK
stack now run automatically via cron rather than requiring manual
execution - see [`detection/CRON_SETUP.md`](../detection/CRON_SETUP.md)
for the full crontab and rationale for each interval. In short: port
scan/brute force/DoS run every 2 minutes (short lookback windows), SQLi/
DNS tunneling/ML run every 5 minutes (longer lookback windows), and
Elasticsearch/Logstash/Kibana are started 45 seconds after boot via
`@reboot`.

## Next Steps

1. Evaluate the full pipeline against the CIC-IDS2017 benchmark dataset to
   produce quantitative precision/recall/F1 figures per attack class.
2. Retrain the ML anomaly model on a verified clean traffic window to
   correct the training-data contamination issue described above.
3. Use the Community ID values already logged by both Suricata and Zeek
   to build genuine cross-engine alert correlation.
4. (Optional) Extend the Logstash pipeline to ingest Zeek's `http.log` and
   `dns.log`, enabling payload-level Python detection for SQLi/DNS
   tunneling instead of the current Suricata-alert-correlation approach.
5. (Optional) Implement threat intelligence enrichment (e.g., AbuseIPDB)
   for source IPs seen in alerts.
