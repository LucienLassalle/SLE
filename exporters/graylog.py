"""
GrayLog exporter for SLE
Uses GELF (Graylog Extended Log Format) over HTTP
"""

import time
import logging
import requests
import socket
from typing import Dict, Any

from exporters.base import BaseExporter


logger = logging.getLogger('SLE.GraylogExporter')


class GraylogExporter(BaseExporter):
    """Export logs to GrayLog using GELF HTTP"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get('url', '').rstrip('/')
        self.timeout = config.get('timeout', 5)
        self.hostname = config.get('hostname', socket.gethostname())
        
    def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """Send a log entry to GrayLog using GELF format"""
        try:
            # GELF format (http://docs.graylog.org/en/latest/pages/gelf.html)
            gelf_message = {
                'version': '1.1',
                'host': self.hostname,
                'short_message': log_entry['line'],
                'timestamp': time.time(),
                'level': 6,  # Info level
                '_job': 'sle',
                '_service': log_entry['name'],
                '_category': log_entry['subname'],
                '_filepath': log_entry['filepath']
            }
            
            # Send to GrayLog GELF HTTP endpoint
            response = requests.post(
                f"{self.base_url}/gelf",
                json=gelf_message,
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            )
            
            if response.status_code == 202:
                return True
            else:
                logger.warning(f"GrayLog returned status {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending to GrayLog: {e}")
            return False
    
    def get_name(self) -> str:
        """Get exporter name"""
        return "graylog"
