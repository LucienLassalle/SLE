"""
Kafka exporter for SLE
"""

import time
import logging
import json
from typing import Dict, Any

from exporters.base import BaseExporter


logger = logging.getLogger('SLE.KafkaExporter')


class KafkaExporter(BaseExporter):
    """Export logs to Kafka"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bootstrap_servers = config.get('url', '').replace('http://', '').replace('https://', '')
        self.topic = config.get('topic', 'sle-logs')
        self.timeout = config.get('timeout', 5)
        
        # Import kafka-python only if needed
        try:
            from kafka import KafkaProducer
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers.split(','),
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                request_timeout_ms=self.timeout * 1000
            )
        except ImportError:
            logger.error("kafka-python library not installed. Install it with: pip install kafka-python")
            self.producer = None
        except Exception as e:
            logger.error(f"Error initializing Kafka producer: {e}")
            self.producer = None
        
    def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """Send a log entry to Kafka"""
        if not self.producer:
            return False
            
        try:
            # Kafka message
            message = {
                'timestamp': time.time(),
                'message': log_entry['line'],
                'job': 'sle',
                'service': log_entry['name'],
                'category': log_entry['subname'],
                'filepath': log_entry['filepath']
            }
            
            # Send to Kafka
            future = self.producer.send(self.topic, value=message)
            future.get(timeout=self.timeout)
            
            return True
                
        except Exception as e:
            logger.error(f"Error sending to Kafka: {e}")
            return False
    
    def get_name(self) -> str:
        """Get exporter name"""
        return "kafka"
