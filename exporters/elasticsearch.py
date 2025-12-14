"""
ElasticSearch/OpenSearch exporter for SLE
Supports both ElasticSearch and OpenSearch
"""

import time
import logging
import requests
from typing import Dict, Any
from datetime import datetime, timezone

from exporters.base import BaseExporter


logger = logging.getLogger('SLE.ElasticsearchExporter')


class ElasticsearchExporter(BaseExporter):
    """Export logs to ElasticSearch or OpenSearch"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get('url', '').rstrip('/')
        self.timeout = config.get('timeout', 5)
        self.index_prefix = config.get('index_prefix', 'sle-logs')
        self.username = config.get('username')
        self.password = config.get('password')
        
    def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """Send a log entry to ElasticSearch/OpenSearch"""
        try:
            # Create index name with date (e.g., sle-logs-2024-12-14)
            index_name = f"{self.index_prefix}-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
            
            # ElasticSearch document
            document = {
                '@timestamp': datetime.now(timezone.utc).isoformat(),
                'message': log_entry['line'],
                'job': 'sle',
                'service': log_entry['name'],
                'category': log_entry['subname'],
                'filepath': log_entry['filepath']
            }
            
            # Prepare auth if provided
            auth = None
            if self.username and self.password:
                auth = (self.username, self.password)
            
            # Send to ElasticSearch
            response = requests.post(
                f"{self.base_url}/{index_name}/_doc",
                json=document,
                auth=auth,
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            )
            
            if response.status_code in [200, 201]:
                return True
            else:
                logger.warning(f"ElasticSearch returned status {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending to ElasticSearch: {e}")
            return False
    
    def get_name(self) -> str:
        """Get exporter name"""
        return "elasticsearch"
