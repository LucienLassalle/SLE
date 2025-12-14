"""
FluentBit/Fluent Bit exporter for SLE
Uses HTTP input plugin
"""

import time
import logging
import requests
from typing import Dict, Any
from datetime import datetime

from exporters.base import BaseExporter


logger = logging.getLogger('SLE.FluentBitExporter')


class FluentBitExporter(BaseExporter):
    """Export logs to FluentBit using HTTP input"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get('url', '').rstrip('/')
        self.timeout = config.get('timeout', 5)
        self.tag = config.get('tag', 'sle')
        
    def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """Send a log entry to FluentBit"""
        try:
            # FluentBit JSON format
            log_record = [{
                'date': time.time(),
                'log': log_entry['line'],
                'job': 'sle',
                'service': log_entry['name'],
                'category': log_entry['subname'],
                'filepath': log_entry['filepath']
            }]
            
            response = requests.post(
                f"{self.base_url}/{self.tag}",
                json=log_record,
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            )
            
            if response.status_code in [200, 201, 204]:
                return True
            else:
                logger.warning(f"FluentBit returned status {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending to FluentBit: {e}")
            return False
    
    def get_name(self) -> str:
        """Get exporter name"""
        return "fluentbit"
