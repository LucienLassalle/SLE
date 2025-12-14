"""
VictoriaLogs exporter for SLE
"""

import time
import logging
import requests
from typing import Dict, Any

from exporters.base import BaseExporter


logger = logging.getLogger('SLE.VictoriaLogsExporter')


class VictoriaLogsExporter(BaseExporter):
    """Export logs to VictoriaLogs"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get('url', '').rstrip('/')
        self.push_url = f"{self.base_url}/insert/jsonline"
        self.timeout = config.get('timeout', 5)
        
    def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """Send a log entry to VictoriaLogs"""
        try:
            # VictoriaLogs JSON line format
            log_record = {
                '_time': int(time.time() * 1e9),  # Timestamp in nanoseconds
                '_msg': log_entry['line'],
                'job': 'sle',
                'service': log_entry['name'],
                'category': log_entry['subname'],
                'filepath': log_entry['filepath']
            }
            
            response = requests.post(
                self.push_url,
                json=log_record,
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            )
            
            if response.status_code in [200, 204]:
                return True
            else:
                logger.warning(f"VictoriaLogs returned status {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending to VictoriaLogs: {e}")
            return False
    
    def get_name(self) -> str:
        """Get exporter name"""
        return "victorialogs"
