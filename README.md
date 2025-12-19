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
✅ **Glob patterns** - Wildcard support for log file paths (`/var/log/*.log`, `/app/*/logs/*.log`)  
✅ **Rate limiting** - Control log throughput per source (logs/second)  
✅ **Batching** - Group logs for efficient sending (configurable buffer size)  
✅ **Auto-reload** - Automatically detect new files matching glob patterns (no restart needed)
✅ **Disk buffering (WAL)** - At-least-once delivery with Write-Ahead Log for critical logs

## What SLE Does NOT Do

❌ **No log rotation** - Use `logrotate` for that  
❌ **No log parsing/filtering** - Sends raw logs (except level extraction)  
❌ **No encryption** - Use TLS-enabled backends or reverse proxy  
❌ **No authentication** - Relies on backend authentication  
❌ **No log archival** - Use backend retention policies  

## Features

- Real-time log export (tail -f style)
- Systemd journal (journald) monitoring
- Multiple backend support
- Glob pattern support with auto-reload
- Smart timestamp and log level detection
- Simple configuration (JSON/YAML)
- Custom labels support
- Rate limiting and batching
- Disk buffering (WAL) for at-least-once delivery
- Resilient error handling
- Systemd integration

## Quick Start

```bash
# Install
pip3 install -r requirements.txt
sudo mkdir -p /opt/sle /etc/sle.d /var/lib/sle/buffer
sudo cp sle.py config_loader.py file_watcher.py journald_watcher.py disk_buffer.py /opt/sle/
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
AUTO_RELOAD (optional) → Auto-reload interval in seconds (default.json only)
QUEUE_SIZE (optional)  → Queue size limit (default.json only)
  ↓
SERVICE_NAME (mandatory) → Service identifier
  ↓
CATEGORY (mandatory)     → Log category
  ↓
path_file (mandatory)    → Absolute path to log file
                           Supports glob patterns: *, ?, []
delimiter (optional)     → Line delimiter (default: \n)
labels (optional)        → Custom labels dict
rate_limit (optional)    → Max logs/sec (enforced per file)
buffer_size (optional)   → Batch size (logs grouped before sending)
disk_buffer (optional)   → DROP (default) or DISK (at-least-once)
```

### Glob Pattern Support (Wildcards)

**SLE supports wildcards in file paths** to monitor multiple files matching a pattern:

- `*` - Matches any characters (except path separator)
- `?` - Matches a single character
- `[]` - Matches character ranges
- `**` - Matches any files and zero or more directories (recursive)

**Examples:**

```json
{
    "LOKI_IP": "http://loki:3100",
    "docker": {
        "CONTAINERS": {
            "path_file": "/var/lib/docker/containers/*/*.log",
            "disk_buffer": "DISK"
        }
    },
    "apps": {
        "ALL_LOGS": {
            "path_file": "/var/log/apps/**/*.log",
            "rate_limit": 500,
            "buffer_size": 100
        }
    },
    "nginx": {
        "ACCESS": {
            "path_file": "/var/log/nginx/access*.log",
            "disk_buffer": "DROP"
        }
    }
}
```

**Benefits:**
- ✅ Monitor all files matching pattern automatically
- ✅ Works with auto-reload to detect new files dynamically
- ✅ Perfect for container logs, rotated logs, multi-instance apps
- ✅ Each matched file is monitored independently

**Notes:**
- Pattern is resolved at startup and during auto-reload cycles
- If pattern matches no files, a warning is logged and the entry is skipped
- Each matched file gets its own watcher and rate limit/buffer (if specified)
- Enable `AUTO_RELOAD` in default.json to automatically detect new files

### Auto-Reload Support

**Automatically detect new files matching glob patterns without restart!**

Enable auto-reload in `default.json` or `default.yml` to periodically check for new files:

```json
{
    "LOKI_IP": "http://localhost:3100",
    "AUTO_RELOAD": 300,
    "JOURNALCTL": "off"
}
```

**Configuration:**
- `AUTO_RELOAD` - Interval in seconds (e.g., 300 = check every 5 minutes)
- Default: 0 (disabled)
- Only works in `default.json` or `default.yml`

**Benefits:**
- ✅ New files matching glob patterns are automatically monitored
- ✅ No service restart needed when containers/apps are deployed
- ✅ Perfect for dynamic environments (Docker, Kubernetes, auto-scaling)
- ✅ Each new file gets its own watcher with configured rate limits/buffers

**Example Use Cases:**
- Docker: `/var/lib/docker/containers/*/*.log` - auto-detect new containers
- Rotated logs: `/var/log/nginx/access*.log` - catch rotated files
- Multi-instance apps: `/var/log/apps/**/*.log` - monitor new app instances

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
    rate_limit: 500
    buffer_size: 50

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
| `AUTO_RELOAD` | Optional | Auto-reload interval in seconds (**default.json only**) | `300` (5 minutes) |
| `QUEUE_SIZE` | Optional | Queue size limit (**default.json only**, works with `disk_buffer`) | `10000` (default: 5000 hard limit) |
| `JOURNALCTL` | Optional | Enable journald monitoring (**default.json only**) | `"on"` or `"off"` |
| `service_name` | **Mandatory** | Service identifier | `nginx`, `apache2`, `myapp` |
| `category` | **Mandatory** | Log category | `ACCESS`, `ERROR`, `SYSTEM` |
| `path_file` | **Mandatory** | Absolute path to log file (supports wildcards: `*`, `?`, `[]`, `**`) | `/var/log/nginx/*.log`, `/app/**/logs/*.log` |
| `delimiter` | Optional | Line delimiter (default: `\n`) | `\n`, `\r\n`, `\|\|` |
| `labels` | Optional | Custom labels - **any key/value pairs you want** | `{"environment": "prod"}`, `{"team": "ops"}`, `{"priority": "high"}` |
| `rate_limit` | Optional | Max logs per second (int/float) - **enforced per file** | `1000`, `500.5` |
| `buffer_size` | Optional | Batch size (int) - **logs grouped before sending** | `100`, `50` |
| `disk_buffer` | Optional | Buffering strategy: `DROP` or `DISK` (default: `DROP`) | `"DISK"` for at-least-once delivery |

**Important Notes:**
- `labels` can contain **any custom key/value pairs** - they become searchable labels in your backend (e.g., Loki)
- `rate_limit` uses token bucket algorithm - excess logs are dropped (DROP) or saved to disk (DISK)
- `buffer_size` groups logs for efficient batch sending - buffers are flushed when full or periodically
- `disk_buffer` with `DISK` enables Write-Ahead Log for at-least-once delivery guarantee
- Both `rate_limit` and `buffer_size` are applied **per matched file** when using glob patterns
- `AUTO_RELOAD`, `QUEUE_SIZE`, and `JOURNALCTL` are **only** read from `default.json` or `default.yml`
- Without `QUEUE_SIZE`: built-in hard limit of 5000 logs, then queue is cleared (logs dropped)
- With `QUEUE_SIZE`: custom limit, logs can be saved to disk if `disk_buffer: "DISK"` is configured

### Queue Management & Backpressure

**SLE monitors the internal queue to prevent memory overflow.**

⚠️ **IMPORTANT:** `QUEUE_SIZE` **MUST** be configured in `default.json` or `default.yml` only. It will be ignored in other configuration files.

#### Default Behavior (No QUEUE_SIZE configured in default.json)

When `QUEUE_SIZE` is not set in `default.json`, SLE uses a **built-in hard limit of 5000 logs**:

```json
{
    "LOKI_IP": "http://localhost:3100",
    "JOURNALCTL": "off"
}
```

**Automatic queue monitoring:**
- ✅ **WARNING** at 20%: 1000 logs
- ✅ **WARNING** at 40%: 2000 logs  
- ✅ **WARNING** at 60%: 3000 logs
- ✅ **WARNING** at 80%: 4000 logs
- 🔴 **CRITICAL** at 100%: 5000 logs → **QUEUE CLEARED**
- ⚠️ All 5000 logs in queue are **IMMEDIATELY DROPPED**

**This protects SLE from memory exhaustion (OOM kill) but logs are lost.**

#### With QUEUE_SIZE in default.json

To enable disk buffering when queue is full, configure `QUEUE_SIZE` in `default.json`:

```json
{
    "LOKI_IP": "http://localhost:3100",
    "QUEUE_SIZE": 10000,
    "JOURNALCTL": "off"
}
```

Then configure `disk_buffer: "DISK"` for critical log sources:

```json
{
    "LOKI_IP": "http://localhost:3100",
    "QUEUE_SIZE": 10000,
    "JOURNALCTL": "off",
    "nginx": {
        "ACCESS": {
            "path_file": "/var/log/nginx/access.log",
            "disk_buffer": "DROP"
        },
        "ERROR": {
            "path_file": "/var/log/nginx/error.log",
            "disk_buffer": "DISK"
        }
    }
}
```

**Queue management with QUEUE_SIZE:**
- ✅ **WARNING** at 20%: 2000 logs
- ✅ **WARNING** at 40%: 4000 logs
- ✅ **WARNING** at 60%: 6000 logs
- ✅ **WARNING** at 80%: 8000 logs
- 🔴 **CRITICAL** at 100%: 10000 logs
- 💾 Logs with `disk_buffer: "DISK"` → **saved to disk for replay**
- ⚠️ Logs with `disk_buffer: "DROP"` → **dropped**

**Key Points:**
- `QUEUE_SIZE` **MUST be in `default.json` or `default.yml`** - ignored elsewhere
- Without `QUEUE_SIZE`: hard limit of 5000 logs, then **clear queue** (all dropped)
- With `QUEUE_SIZE`: custom limit, logs saved to disk if `disk_buffer: "DISK"`
- Warnings at 20% intervals are **automatic and non-configurable**
- Protects SLE from memory exhaustion (OOM)
- See `examples/default-with-queue.json` for complete example

**Use Cases:**
- **No QUEUE_SIZE**: Simple deployments, logs are not critical
- **QUEUE_SIZE + DISK**: Production, compliance logs, temporary backend outages

### Disk Buffering (WAL) - At-Least-Once Delivery

**Problem:** By default, SLE drops logs when:
- Backend is down or unreachable
- Rate limit is exceeded
- Network issues occur

**Solution:** Enable disk buffering for critical logs that must not be lost.

```json
{
    "LOKI_IP": "http://localhost:3100",
    "nginx": {
        "ACCESS": {
            "path_file": "/var/log/nginx/access.log",
            "disk_buffer": "DROP"
        },
        "ERROR": {
            "path_file": "/var/log/nginx/error.log",
            "disk_buffer": "DISK"
        }
    }
}
```

**How it works:**
1. When sending fails or rate limit is hit, logs are written to disk (`/var/lib/sle/buffer/`)
2. Logs are persisted with `fsync()` for durability
3. On startup, buffered logs are replayed automatically
4. Only deleted after successful delivery

**Options:**
- `disk_buffer: "DROP"` (default) - Drop logs on failure/rate limit
- `disk_buffer: "DISK"` - Save to disk, replay later (at-least-once)

**Benefits:**
- ✅ No log loss during backend downtime
- ✅ At-least-once delivery guarantee
- ✅ Survives SLE restarts
- ✅ Suitable for compliance/regulatory logs
- ✅ Per-file granularity (mix DROP and DISK)

**Storage Location:**
- Buffers stored in `/var/lib/sle/buffer/<service>/<category>/`
- Each log is a separate file with sequence number
- Automatically cleaned up after successful delivery

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

# Check disk buffer usage
sudo du -sh /var/lib/sle/buffer/

# Monitor queue warnings
sudo journalctl -u sle -f | grep -i "queue"
```

## Security Considerations

### File Permissions

SLE requires appropriate permissions:
- **Read access**: to log files (e.g., `/var/log/nginx/*.log`)
- **Write access**: to disk buffer directory (`/var/lib/sle/buffer/`)

**Recommended setup:**
```bash
# Create dedicated user
sudo useradd -r -s /bin/false sle

# Set ownership
sudo chown -R sle:sle /var/lib/sle /opt/sle

# Restrict buffer directory
sudo chmod 700 /var/lib/sle/buffer
```

### Network Security

- **No TLS**: SLE doesn't encrypt data in transit
- **Solution**: Use TLS-enabled backends or reverse proxy
- **Backend auth**: SLE relies on backend authentication

### Configuration Security

- **Path traversal protection**: `..` and `/` stripped from service/category names
- **Type validation**: All config values validated
- **No shell execution**: Glob patterns use Python stdlib only

### Disk Buffer Limits

- **No size limit**: Disk buffer can grow indefinitely
- **Monitoring**: Check `/var/lib/sle/buffer/` regularly
- **Cleanup**: Old files (>24h) automatically removed

## Architecture

```
Config (JSON/YAML) → ConfigLoader → ExporterFactory
                                         ↓
LogFileWatcher (tail -f) → Queue → Exporter → Backend
```

## Update

```bash
sudo systemctl stop sle
sudo cp sle.py config_loader.py file_watcher.py journald_watcher.py disk_buffer.py /opt/sle/
sudo cp -r exporters /opt/sle/
sudo systemctl start sle
```

## Uninstall

```bash
sudo systemctl stop sle
sudo systemctl disable sle
sudo rm /etc/systemd/system/sle.service
sudo rm -rf /opt/sle /etc/sle.d /var/lib/sle
sudo systemctl daemon-reload
```

## License

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

---

**Version**: 1.0.2
