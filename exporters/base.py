"""
Base exporter class for SLE
All exporters should inherit from this class
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseExporter(ABC):
    """Base class for all log exporters"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the exporter
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        
    @abstractmethod
    def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """
        Send a log entry to the backend
        
        Args:
            log_entry: Dictionary containing log information
                - line: The log line content
                - name: Service name
                - subname: Sub-category name
                - filepath: Source file path
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Get the exporter name
        
        Returns:
            Exporter name (e.g., 'loki', 'elasticsearch', 'syslog')
        """
        pass
