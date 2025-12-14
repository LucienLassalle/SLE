"""
Azure Monitor exporter for SLE
"""

import time
import logging
from typing import Dict, Any
from datetime import datetime

from exporters.base import BaseExporter


logger = logging.getLogger('SLE.AzureExporter')


class AzureExporter(BaseExporter):
    """Export logs to Azure Monitor"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.workspace_id = config.get('workspace_id')
        self.shared_key = config.get('shared_key')
        self.log_type = config.get('log_type', 'SLELogs')
        
        # Import azure-monitor-ingestion only if needed
        try:
            import requests
            import base64
            import hmac
            import hashlib
            self.has_deps = True
        except ImportError:
            logger.error("Required libraries not available for Azure exporter")
            self.has_deps = False
    
    def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """Send a log entry to Azure Monitor"""
        if not self.has_deps or not self.workspace_id or not self.shared_key:
            return False
            
        try:
            import requests
            import base64
            import hmac
            import hashlib
            import json
            
            # Azure Monitor log entry
            log_data = [{
                'TimeGenerated': datetime.utcnow().isoformat(),
                'Message': log_entry['line'],
                'Job': 'sle',
                'Service': log_entry['name'],
                'Category': log_entry['subname'],
                'FilePath': log_entry['filepath']
            }]
            
            body = json.dumps(log_data)
            
            # Build signature
            method = 'POST'
            content_length = len(body)
            content_type = 'application/json'
            resource = '/api/logs'
            rfc1123date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
            
            string_to_hash = f"{method}\n{content_length}\n{content_type}\nx-ms-date:{rfc1123date}\n{resource}"
            bytes_to_hash = bytes(string_to_hash, 'UTF-8')
            decoded_key = base64.b64decode(self.shared_key)
            encoded_hash = base64.b64encode(hmac.new(decoded_key, bytes_to_hash, digestmod=hashlib.sha256).digest()).decode()
            
            authorization = f"SharedKey {self.workspace_id}:{encoded_hash}"
            
            # Send to Azure
            url = f"https://{self.workspace_id}.ods.opinsights.azure.com{resource}?api-version=2016-04-01"
            headers = {
                'content-type': content_type,
                'Authorization': authorization,
                'Log-Type': self.log_type,
                'x-ms-date': rfc1123date
            }
            
            response = requests.post(url, data=body, headers=headers)
            
            if response.status_code == 200:
                return True
            else:
                logger.warning(f"Azure Monitor returned status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending to Azure Monitor: {e}")
            return False
    
    def get_name(self) -> str:
        """Get exporter name"""
        return "azure"
