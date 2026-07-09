# A Hybrid Signature- and Anomaly-Based Intrusion Detection Framework
### Using Suricata, Zeek, and Machine Learning

**Status: Draft — in progress. Sections are filled in as each component is completed.**

---

## Abstract

*(To be finalized once all components are complete.)*

Modern network intrusion detection systems (NIDS) generally fall into two
categories: signature-based systems, which detect known attack patterns with
high precision but cannot generalize to novel threats, and anomaly-based
systems, which use statistical or machine learning models to flag deviations
from normal behavior but often suffer from high false-positive rates. This
paper presents the design and implementation of a hybrid NIDS that combines
Suricata (signature-based detection), Zeek (protocol-level logging), and a
machine learning anomaly detection layer, unified through an ELK-based
pipeline and a correlation/alerting API. We evaluate the platform's detection
accuracy against simulated attacks and, where applicable, the CIC-IDS2017
benchmark dataset.

## 1. Introduction

### 1.1 Problem Statement
Small organizations, students, and independent researchers often lack access
to commercial SIEM/NIDS platforms due to cost. Open-source tools like
Suricata and Zeek provide strong detection primitives individually, but
lack an integrated pipeline that combines their strengths with modern
anomaly detection and presents results in a usable, correlated form.

### 1.2 Contribution
This work contributes:
1. An integrated architecture combining Suricata (signatures), Zeek
   (protocol/connection context), and ML-based anomaly detection.
2. A custom Suricata ruleset targeting five attack classes: DoS, port
   scanning, brute force, SQL injection, and DNS tunneling.
3. An evaluation methodology using both live attack simulation in a
   controlled lab and (planned) benchmark dataset evaluation.

## 2. Related Work

*(TODO: literature review — Suricata vs Snort vs Zeek comparisons, prior
hybrid IDS work, CIC-IDS2017 baseline papers.)*

## 3. System Architecture
Network Traffic
|
v
[Suricata] --eve.json-->  [Logstash] --> [Elasticsearch] --> [Kibana Dashboard]
[Zeek]     --conn/dns/http logs-->  |            ^
|                              |            |
v                              v            |
[Python Detectors]  <-------->  [ML Anomaly Engine]
|                              |
+------------> [Alert Correlation Layer] ----> [FastAPI] --> Dashboard/Alerts/Timeline
Full component breakdown is in [architecture.md](architecture.md).

## 4. Methodology

### 4.1 Lab Environment
- **Sensor host:** Kali Linux (VMware Workstation), monitoring interface
  `eth0`, bridged to the physical network (`192.168.100.0/24`).
- **Attacker host:** Debian (VirtualBox), bridged to the same network segment
  to enable realistic inter-VM traffic capture.
- **Rationale:** Both signature and anomaly detection require traffic that
  actually traverses a monitored interface; same-host loopback traffic
  (e.g., scanning `127.0.0.1` or a self-assigned IP) does not exercise the
  af-packet capture path and was explicitly avoided.

### 4.2 Custom Detection Rules
A ruleset of 12 custom Suricata rules (SID range 9000001–9000041) was
authored to cover:
- **DoS/Flood:** SYN flood, ICMP flood, UDP flood via `threshold` tracking
  by source IP.
- **Port Scan:** high SYN rate to many destination ports; NULL/XMAS scan
  flag combinations.
- **Brute Force:** repeated SSH/FTP SYN attempts and HTTP login endpoint
  requests within a time window.
- **SQL Injection:** HTTP URI pattern matching for UNION/SELECT and
  tautology-style payloads.
- **DNS Tunneling:** abnormally long query names and high-volume TXT record
  queries.

Full rule source: [`capture/suricata/rules/custom.rules`](../capture/suricata/rules/custom.rules).

## 5. Implementation

### 5.1 Suricata Deployment — ✅ Complete
Suricata 8.0.5 was deployed on the sensor host with `HOME_NET` set to
`192.168.0.0/16,10.0.0.0/8,172.16.0.0/12` and af-packet capture bound to
`eth0`. The custom ruleset was integrated by adding `custom.rules` to the
`rule-files` list in `suricata.yaml`, and placing the file in the path
resolved by `default-rule-path` (`/var/lib/suricata/rules/` in this
deployment — note this can differ from the commonly documented
`/etc/suricata/rules/` depending on distribution packaging).

### 5.2 Zeek Deployment — ⬜ In progress

### 5.3 Logstash / Elasticsearch Pipeline — ⬜ In progress

### 5.4 Python Detection Modules — ⬜ Not started

### 5.5 ML Anomaly Detection — ⬜ Not started

### 5.6 API and Dashboard — ⬜ Not started

## 6. Results

### 6.1 Live Attack Simulation — Port Scan Detection

A TCP SYN scan (`nmap -sS -Pn -p 1-100`) was launched from the Debian
attacker host against the Kali sensor host. Suricata's built-in decoder-level
scan detection (SID 3400002) and the project's custom port-scan rule
(SID 9000010) both triggered successfully, confirming the full detection
pipeline — traffic capture, rule matching, and alert logging — functions
end-to-end.

Excerpt from `fast.log`:

