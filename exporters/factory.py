"""
Exporter factory for SLE
Creates appropriate exporter instances based on type
"""

import logging
from typing import Dict, Any, Optional

from exporters.base import BaseExporter
from exporters.loki import LokiExporter
from exporters.elasticsearch import ElasticsearchExporter
from exporters.opensearch import OpenSearchExporter
from exporters.graylog import GraylogExporter
from exporters.victorialogs import VictoriaLogsExporter
from exporters.clickhouse import ClickHouseExporter
from exporters.fluentbit import FluentBitExporter
from exporters.kafka import KafkaExporter
from exporters.cloudwatch import CloudWatchExporter
from exporters.gcp import GCPExporter
from exporters.azure import AzureExporter


logger = logging.getLogger('SLE.ExporterFactory')


class ExporterFactory:
    """Factory for creating exporter instances"""
    
    # Registry of available exporters
    _exporters = {
        'loki': LokiExporter,
        'elastic': ElasticsearchExporter,
        'elasticsearch': ElasticsearchExporter,
        'opensearch': OpenSearchExporter,
        'graylog': GraylogExporter,
        'victorialogs': VictoriaLogsExporter,
        'clickhouse': ClickHouseExporter,
        'fluentbit': FluentBitExporter,
        'kafka': KafkaExporter,
        'cloudwatch': CloudWatchExporter,
        'gcp': GCPExporter,
        'azure': AzureExporter,
    }
    
    @classmethod
    def create(cls, exporter_type: str, config: Dict[str, Any]) -> Optional[BaseExporter]:
        """
        Create an exporter instance
        
        Args:
            exporter_type: Type of exporter (e.g., 'loki', 'elasticsearch')
            config: Configuration dictionary
        
        Returns:
            Exporter instance or None if type is not supported
        """
        exporter_type = exporter_type.lower()
        
        if exporter_type not in cls._exporters:
            logger.error(f"Unknown exporter type: {exporter_type}")
            logger.info(f"Available exporters: {', '.join(cls._exporters.keys())}")
            return None
        
        try:
            exporter_class = cls._exporters[exporter_type]
            return exporter_class(config)
        except Exception as e:
            logger.error(f"Error creating {exporter_type} exporter: {e}")
            return None
    
    @classmethod
    def register(cls, exporter_type: str, exporter_class: type):
        """
        Register a new exporter type
        
        Args:
            exporter_type: Type identifier (e.g., 'myexporter')
            exporter_class: Exporter class (must inherit from BaseExporter)
        """
        if not issubclass(exporter_class, BaseExporter):
            raise ValueError(f"{exporter_class} must inherit from BaseExporter")
        
        cls._exporters[exporter_type.lower()] = exporter_class
        logger.info(f"Registered new exporter: {exporter_type}")
    
    @classmethod
    def list_exporters(cls) -> list:
        """Get list of available exporter types"""
        return list(cls._exporters.keys())
