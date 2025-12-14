"""
GCP Cloud Logging exporter for SLE
"""

import time
import logging
from typing import Dict, Any

from exporters.base import BaseExporter


logger = logging.getLogger('SLE.GCPExporter')


class GCPExporter(BaseExporter):
    """Export logs to GCP Cloud Logging"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.project_id = config.get('project_id')
        self.log_name = config.get('log_name', 'sle-logs')
        
        # Import google-cloud-logging only if needed
        try:
            from google.cloud import logging as gcp_logging
            self.logging_client = gcp_logging.Client(project=self.project_id)
            self.logger = self.logging_client.logger(self.log_name)
        except ImportError:
            logger.error("google-cloud-logging library not installed. Install it with: pip install google-cloud-logging")
            self.logger = None
        except Exception as e:
            logger.error(f"Error initializing GCP logging client: {e}")
            self.logger = None
    
    def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """Send a log entry to GCP Cloud Logging"""
        if not self.logger:
            return False
            
        try:
            # GCP log entry
            self.logger.log_text(
                log_entry['line'],
                severity='INFO',
                labels={
                    'job': 'sle',
                    'service': log_entry['name'],
                    'category': log_entry['subname'],
                    'filepath': log_entry['filepath']
                }
            )
            
            return True
                
        except Exception as e:
            logger.error(f"Error sending to GCP Cloud Logging: {e}")
            return False
    
    def get_name(self) -> str:
        """Get exporter name"""
        return "gcp"
