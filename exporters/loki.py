"""
Grafana Loki exporter for SLE
"""

import time
import re
import logging
import requests
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

from exporters.base import BaseExporter


logger = logging.getLogger('SLE.LokiExporter')


class LokiExporter(BaseExporter):
    """Export logs to Grafana Loki"""
    
    # Regex patterns for log level detection
    LOG_LEVEL_PATTERN = re.compile(
        r'\b(TRACE|DEBUG|INFO|INFORMATION|WARN|WARNING|ERROR|ERR|FATAL|CRITICAL|CRIT|NOTICE|ALERT|EMERG)\b',
        re.IGNORECASE
    )
    
    # Regex patterns for timestamp detection (common formats)
    TIMESTAMP_PATTERNS = [
        # ISO 8601: 2025-10-17T02:26:16+0200 or 2025-10-17T02:26:16Z
        re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d{3,9})?(?:Z|[+-]\d{2}:?\d{2})?'),
        # Syslog: Oct 17 02:26:16 or 2025-10-17 02:26:16
        re.compile(r'^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}|\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}'),
        # Timestamp with milliseconds: 2025-10-17 02:26:16.123
        re.compile(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[.,]\d{3,9}'),
        # [2025-10-17 02:26:16]
        re.compile(r'^\[\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d{3,9})?\]'),
    ]
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.loki_url = config.get('url', '').rstrip('/')
        self.push_url = f"{self.loki_url}/loki/api/v1/push"
        self.timeout = config.get('timeout', 5)
    
    def _parse_log_line(self, line: str) -> Tuple[str, Optional[str], Optional[int]]:
        """
        Parse a log line to extract level, timestamp, and clean content
        
        Returns:
            (cleaned_line, log_level, timestamp_ns)
        """
        log_level = None
        timestamp_ns = None
        
        # 1. Check if line starts with a timestamp
        has_timestamp = False
        for pattern in self.TIMESTAMP_PATTERNS:
            match = pattern.match(line)
            if match:
                has_timestamp = True
                # Extract timestamp string
                ts_str = match.group(0).strip('[]')
                try:
                    # Try to parse the timestamp
                    # Handle various formats
                    for fmt in [
                        '%Y-%m-%dT%H:%M:%S%z',
                        '%Y-%m-%dT%H:%M:%SZ',
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%d %H:%M:%S.%f',
                        '%Y-%m-%dT%H:%M:%S.%f',
                        '%Y-%m-%dT%H:%M:%S.%fZ',
                    ]:
                        try:
                            dt = datetime.strptime(ts_str, fmt)
                            timestamp_ns = int(dt.timestamp() * 1e9)
                            break
                        except ValueError:
                            continue
                except Exception as e:
                    logger.debug(f"Failed to parse timestamp: {ts_str}, error: {e}")
                break
        
        # 2. Extract log level if present
        level_match = self.LOG_LEVEL_PATTERN.search(line)
        if level_match:
            log_level = level_match.group(1).upper()
            # Normalize level names
            if log_level in ['INFORMATION', 'INFORMATIONAL']:
                log_level = 'INFO'
            elif log_level in ['WARN', 'WARNING']:
                log_level = 'WARN'
            elif log_level in ['ERR', 'ERROR']:
                log_level = 'ERROR'
            elif log_level in ['FATAL', 'CRITICAL', 'CRIT']:
                log_level = 'CRITICAL'
            
            # Remove the level from the line to avoid duplication
            line = self.LOG_LEVEL_PATTERN.sub('', line, count=1).strip()
        
        # 3. If no timestamp detected, use current time
        if timestamp_ns is None:
            timestamp_ns = int(time.time() * 1e9)
        
        # Clean up extra whitespace
        line = ' '.join(line.split())
        
        return line, log_level, timestamp_ns
        
    def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """Send a log entry to Loki"""
        try:
            # Parse the log line intelligently
            cleaned_line, log_level, timestamp_ns = self._parse_log_line(log_entry['line'])
            
            # Build stream labels
            stream = {
                "job": "sle",
                "name": log_entry['name'],
                "subname": log_entry['subname'],
                "filepath": log_entry['filepath']
            }
            
            # Add log level as label if detected
            if log_level:
                stream["level"] = log_level
            
            # Add custom labels if present
            if 'labels' in log_entry and log_entry['labels']:
                stream.update(log_entry['labels'])
            
            # Loki format
            payload = {
                "streams": [
                    {
                        "stream": stream,
                        "values": [
                            [
                                str(timestamp_ns),  # Use detected or current timestamp
                                cleaned_line  # Use cleaned line without level duplication
                            ]
                        ]
                    }
                ]
            }
            
            response = requests.post(
                self.push_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            )
            
            if response.status_code == 204:
                return True
            else:
                logger.warning(f"Loki returned status {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending to Loki: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending to Loki: {e}")
            return False
    
    def get_name(self) -> str:
        """Get exporter name"""
        return "loki"
