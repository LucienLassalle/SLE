"""
AWS CloudWatch Logs exporter for SLE
"""

import time
import logging
from typing import Dict, Any
from datetime import datetime

from exporters.base import BaseExporter


logger = logging.getLogger('SLE.CloudWatchExporter')


class CloudWatchExporter(BaseExporter):
    """Export logs to AWS CloudWatch Logs"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.log_group = config.get('log_group', '/sle/logs')
        self.region = config.get('region', 'us-east-1')
        
        # Import boto3 only if needed
        try:
            import boto3
            self.client = boto3.client('logs', region_name=self.region)
            
            # Create log group if it doesn't exist
            try:
                self.client.create_log_group(logGroupName=self.log_group)
            except self.client.exceptions.ResourceAlreadyExistsException:
                pass
                
        except ImportError:
            logger.error("boto3 library not installed. Install it with: pip install boto3")
            self.client = None
        except Exception as e:
            logger.error(f"Error initializing CloudWatch client: {e}")
            self.client = None
    
    def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """Send a log entry to CloudWatch Logs"""
        if not self.client:
            return False
            
        try:
            log_stream = f"{log_entry['name']}/{log_entry['subname']}"
            
            # Create log stream if it doesn't exist
            try:
                self.client.create_log_stream(
                    logGroupName=self.log_group,
                    logStreamName=log_stream
                )
            except self.client.exceptions.ResourceAlreadyExistsException:
                pass
            
            # Put log event
            self.client.put_log_events(
                logGroupName=self.log_group,
                logStreamName=log_stream,
                logEvents=[{
                    'timestamp': int(time.time() * 1000),
                    'message': log_entry['line']
                }]
            )
            
            return True
                
        except Exception as e:
            logger.error(f"Error sending to CloudWatch: {e}")
            return False
    
    def get_name(self) -> str:
        """Get exporter name"""
        return "cloudwatch"
