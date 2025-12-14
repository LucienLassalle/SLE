"""
ClickHouse exporter for SLE
"""

import time
import logging
import requests
from typing import Dict, Any
from datetime import datetime

from exporters.base import BaseExporter


logger = logging.getLogger('SLE.ClickHouseExporter')


class ClickHouseExporter(BaseExporter):
    """Export logs to ClickHouse"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get('url', '').rstrip('/')
        self.timeout = config.get('timeout', 5)
        self.database = config.get('database', 'logs')
        self.table = config.get('table', 'sle_logs')
        self.username = config.get('username', 'default')
        self.password = config.get('password', '')
        
    def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """Send a log entry to ClickHouse"""
        try:
            # ClickHouse INSERT query
            query = f"""
            INSERT INTO {self.database}.{self.table} 
            (timestamp, message, job, service, category, filepath) 
            VALUES
            """
            
            # Format values
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            values = f"('{timestamp}', '{self._escape_sql(log_entry['line'])}', 'sle', '{log_entry['name']}', '{log_entry['subname']}', '{log_entry['filepath']}')"
            
            # Send to ClickHouse
            response = requests.post(
                self.base_url,
                params={
                    'query': query + values,
                    'user': self.username,
                    'password': self.password
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return True
            else:
                logger.warning(f"ClickHouse returned status {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending to ClickHouse: {e}")
            return False
    
    def _escape_sql(self, text: str) -> str:
        """Escape SQL special characters"""
        return text.replace("'", "''").replace("\\", "\\\\")
    
    def get_name(self) -> str:
        """Get exporter name"""
        return "clickhouse"
