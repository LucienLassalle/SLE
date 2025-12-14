# SLE - Simple Log Exporter

Lightweight Python service that exports system logs to multiple backends in real-time.

[![Tests](https://github.com/LucienLassalle/SLE/workflows/SLE%20Tests/badge.svg)](https://github.com/LucienLassalle/SLE/actions)

## What SLE Does

✅ **Real-time log monitoring** - Watches log files as they grow (like `tail -f`)  
✅ **Systemd journal support** - Monitors journald logs via `journalctl`  
✅ **Multiple backends** - Exports to Loki, ElasticSearch, Kafka, etc.  
✅ **High Availability** - Send same logs to multiple backend instances (list support)  
✅ **Smart log parsing** - Auto-detects timestamps and log levels  
✅ **Custom labels** - Add metadata to logs (environment, team, etc.)  
✅ **Multiple formats** - JSON, YAML, YML configuration files  
✅ **Resilient** - Continues on errors, reconnects automatically  

## What SLE Does NOT Do

❌ **No log rotation** - Use `logrotate` for that  
❌ **No log parsing/filtering** - Sends raw logs (except level extraction)  
❌ **No batching yet** - Sends logs one by one (buffer_size parsed but not implemented)  
❌ **No rate limiting yet** - rate_limit parsed but not implemented  
❌ **No encryption** - Use TLS-enabled backends or reverse proxy  
❌ **No authentication** - Relies on backend authentication  
❌ **No log archival** - Use backend retention policies  

## Features

- Real-time log export (tail -f style)
- Systemd journal (journald) monitoring
- Multiple backend support
- Smart timestamp and log level detection
- Simple configuration (JSON/YAML)
- Custom labels support
- Resilient error handling
- Systemd integration

## Quick Start

```bash
# Install
pip3 install -r requirements.txt
sudo mkdir -p /opt/sle /etc/sle.d
sudo cp sle.py config_loader.py file_watcher.py journald_watcher.py /opt/sle/
sudo cp -r exporters /opt/sle/
sudo cp sle.service /etc/systemd/system/
sudo systemctl daemon-reload

# Configure (see examples below)
# For journald monitoring:
sudo cp examples/default.json /etc/sle.d/
# For file-based logs:
sudo nano /etc/sle.d/myapp.json

# Start
sudo systemctl start sle
sudo systemctl enable sle
```

## Configuration

Configuration files in `/etc/sle.d/` with `.json`, `.yaml` or `.yml` extension.

### High Availability Support

**Send logs to multiple backend instances:**

SLE supports sending the same logs to multiple backend instances for redundancy and high availability. Simply provide a **list** of URLs instead of a single URL:

```json
{
    "LOKI_IP": [
        "http://loki-primary:3100",
        "http://loki-secondary:3100",
        "http://loki-backup:3100"
    ],
    "myapp": {
        "LOGS": {
            "path_file": "/var/log/myapp.log"
        }
    }
}
```

**Benefits:**
- ✅ Logs sent to ALL specified backends simultaneously
- ✅ If one backend is down, others still receive logs
- ✅ Load balancing across multiple instances
- ✅ Data redundancy for critical logs

**Supported formats:**
- Single URL: `"LOKI_IP": "http://loki:3100"`
- Multiple URLs: `"LOKI_IP": ["http://loki-1:3100", "http://loki-2:3100"]`

### Journald Support (Systemd Journal)

**Special file: `default.json` or `default.yml` only**

To enable systemd journal monitoring, create `/etc/sle.d/default.json`:

```json
{
    "LOKI_IP": "http://localhost:3100",
    "JOURNALCTL": "on"
}
```

**Behavior:**
- **If `default.json` exists WITH `JOURNALCTL: "on"`** → Journald is **enabled**
- **If `default.json` exists WITH `JOURNALCTL: "off"`** → Journald is **disabled**
- **If `default.json` exists WITHOUT `JOURNALCTL` key** → Journald is **disabled**
- **If `default.json` does NOT exist** → Journald is **disabled**

⚠️ **You must explicitly set `JOURNALCTL: "on"` to enable journald monitoring**

**Other settings:**
- **Only works in `default.json` or `default.yml`** - This setting is ignored in other files
- **Monitors all systemd services** - Logs tagged by unit name (nginx.service → NGINX)
- **Optional labels**: Add `"JOURNALCTL_LABELS": {"datacenter": "eu"}` for custom labels

**Example with labels:**
```json
{
    "LOKI_IP": "http://localhost:3100",
    "JOURNALCTL": "on",
    "JOURNALCTL_LABELS": {
        "source": "systemd",
        "host": "prod-server-01"
    }
}
```

### File-Based Log Format

```
BACKEND_IP (optional)  → Backend endpoint(s), determines type
                         Can be a single URL or list of URLs
  ↓
SERVICE_NAME (mandatory) → Service identifier
  ↓
CATEGORY (mandatory)     → Log category
  ↓
path_file (mandatory)    → Absolute path to log file
delimiter (optional)     → Line delimiter (default: \n)
labels (optional)        → Custom labels dict
rate_limit (optional)    → Max logs/sec (parsed, not implemented)
buffer_size (optional)   → Batch size (parsed, not implemented)
```

### File-Based Log Example (JSON)

**Single backend:**
```json
{
    "LOKI_IP": "http://loki:3100",
    "nginx": {
        "ACCESS": {
            "path_file": "/var/log/nginx/access.log"
        }
    }
}
```

**Multiple backends (High Availability):**
```json
{
    "LOKI_IP": [
        "http://loki-1:3100",
        "http://loki-2:3100",
        "http://loki-3:3100"
    ],
    "nginx": {
        "ACCESS": {
            "path_file": "/var/log/nginx/access.log",
            "delimiter": "\n",
            "labels": {
                "environment": "production",
                "datacenter": "eu-west-1",
                "team": "ops"
            },
            "rate_limit": 1000,
            "buffer_size": 100
        },
        "ERROR": {
            "path_file": "/var/log/nginx/error.log",
            "labels": {
                "severity": "high"
            }
        }
    },
    "apache2": {
        "ACCESS": {
            "path_file": "/var/log/apache2/access.log"
        }
    }
}
```

### File-Based Log Example (YAML)

**Single backend:**
```yaml
ELASTIC_IP: "http://elasticsearch:9200"

syslog:
  SYSTEM:
    path_file: "/var/log/syslog"
```

**Multiple backends (High Availability):**
```yaml
# Send logs to multiple ElasticSearch nodes
ELASTIC_IP:
  - "http://es-node-1:9200"
  - "http://es-node-2:9200"
  - "http://es-node-3:9200"

syslog:
  SYSTEM:
    path_file: "/var/log/syslog"
    delimiter: "\n"
    labels:
      environment: "staging"
      component: "system"
    rate_limit: 500(s) - **String or List** - Type extracted from name | `"loki:3100"` or `["loki-1:3100", "loki-2:3100"]

auth:
  LOGIN:
    path_file: "/var/log/auth.log"
    labels:
      team: "security"
      priority: "high"
```

### Configuration Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `*_IP` | Optional | Backend endpoint - Type extracted from name | `LOKI_IP`, `ELASTIC_IP`, `KAFKA_IP` |
| `service_name` | **Mandatory** | Service identifier | `nginx`, `apache2`, `myapp` |
| `category` | **Mandatory** | Log category | `ACCESS`, `ERROR`, `SYSTEM` |
| `path_file` | **Mandatory** | Absolute path to log file | `/var/log/nginx/access.log` |
| `delimiter` | Optional | Line delimiter (default: `\n`) | `\n`, `\r\n`, `\|\|` |
| `labels` | Optional | Custom labels - **any key/value pairs you want** | `{"environment": "prod"}`, `{"team": "ops"}`, `{"priority": "high"}` |
| `rate_limit` | Optional | Max logs per second (int/float) - **parsed but not implemented** | `1000`, `500.5` |
| `buffer_size` | Optional | Batch size (int) - **parsed but not implemented** | `100`, `50` |

**Important Notes:**
- `labels` can contain **any custom key/value pairs** - they become searchable labels in your backend (e.g., Loki)
- `rate_limit` and `buffer_size` are parsed from config but not yet enforced in queue processing

### Supported Backend Fields

| Field | Backend | Status | Additional Deps |
|-------|---------|--------|-----------------|
| `LOKI_IP` | Grafana Loki | ✅ Supported | None |
| `ELASTIC_IP`, `ELASTICSEARCH_IP` | ElasticSearch | ⚠️ Untested | None |
| `OPENSEARCH_IP` | OpenSearch | ⚠️ Untested | None |
| `GRAYLOG_IP` | GrayLog | ⚠️ Untested | None |
| `VICTORIALOGS_IP` | VictoriaLogs | ⚠️ Untested | None |
| `CLICKHOUSE_IP` | ClickHouse | ⚠️ Untested | None |
| `FLUENTBIT_IP` | FluentBit | ⚠️ Untested | None |
| `KAFKA_IP` | Kafka | ⚠️ Untested | `kafka-python` |
| `CLOUDWATCH_IP` | AWS CloudWatch | ⚠️ Untested | `boto3` |
| `GCP_IP` | GCP Cloud Logging | ⚠️ Untested | `google-cloud-logging` |
| `AZURE_IP` | Azure Monitor | ⚠️ Untested | None |

**Note**: Only Grafana Loki is thoroughly tested. Other backends are implemented but untested.

## Service Management

```bash
sudo systemctl start sle         # Start
sudo systemctl stop sle          # Stop
sudo systemctl restart sle       # Restart
sudo systemctl status sle        # Status
sudo journalctl -u sle -f        # Logs
```

## Manual Testing

```bash
sudo python3 /opt/sle/sle.py           # Normal mode
sudo python3 /opt/sle/sle.py --debug   # Debug mode with verbose logging
```

## Smart Log Processing

SLE automatically enhances logs sent to backends:

**Timestamp Detection**
- Detects existing timestamps in logs (ISO 8601, syslog format, etc.)
- Only adds timestamp if not present in log line
- Prevents timestamp duplication

**Log Level Extraction**
- Auto-detects log levels: DEBUG, INFO, WARN, ERROR, CRITICAL, etc.
- Removes level from log text to avoid duplication
- Adds as `level` label in Loki for easy filtering

**Example transformation:**
```
Before: "2025-10-17T02:26:16+0200 INFO Complete!"
After:  
  - Text: "Complete!"
  - Label: level="INFO"
  - Timestamp: 2025-10-17 02:26:16 (extracted from log)
```

## Querying Logs in Loki

```logql
{job="sle"}                                    # All SLE logs
{job="sle", name="nginx"}                      # Specific service (file-based)
{job="sle", name="journald"}                   # All journald logs
{job="sle", name="journald", subname="NGINX"}  # Specific systemd unit
{job="sle", name="nginx", subname="ACCESS"}    # Specific category
{job="sle", level="ERROR"}                     # Only errors
{job="sle", level=~"ERROR|CRITICAL"}           # Errors + critical
{job="sle"} |= "error"                         # Filter by content
```

**Labels automatically added by SLE:**
- `job="sle"` - Identifies SLE logs
- `name="<service>"` - Service name (or "journald")
- `subname="<category>"` - Log category (or systemd unit name in uppercase)
- `filepath="<path>"` - Source file path (or "journald:<unit>")
- `level="<LEVEL>"` - Log level if detected (INFO, ERROR, etc.)
- Custom labels from config `labels` field (if specified)

## Troubleshooting

```bash
# Check service logs
sudo journalctl -u sle -n 100 --no-pager

# Test backend connectivity
curl http://loki:3100/ready

# Check file permissions
sudo ls -la /var/log/nginx/access.log
```

## Architecture

```
Config (JSON/YAML) → ConfigLoader → ExporterFactory
                                         ↓
LogFileWatcher (tail -f) → Queue → Exporter → Backend
```

## Update

```bash
sudo systemctl stop sle
sudo cp sle.py config_loader.py file_watcher.py journald_watcher.py /opt/sle/
sudo cp -r exporters /opt/sle/
sudo systemctl start sle
```

## Uninstall

```bash
sudo systemctl stop sle
sudo systemctl disable sle
sudo rm /etc/systemd/system/sle.service
sudo rm -rf /opt/sle /etc/sle.d
sudo systemctl daemon-reload
```

## License

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

---

**Version**: 1.0.0
