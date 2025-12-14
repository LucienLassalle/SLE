"""
Unit tests for SLE exporters
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys

from exporters.base import BaseExporter
from exporters.loki import LokiExporter
from exporters.elasticsearch import ElasticsearchExporter
from exporters.graylog import GraylogExporter
from exporters.factory import ExporterFactory


class TestExporterFactory(unittest.TestCase):
    """Test exporter factory"""
    
    def test_create_loki_exporter(self):
        """Test creating a Loki exporter"""
        config = {'url': 'http://loki:3100'}
        exporter = ExporterFactory.create('loki', config)
        self.assertIsInstance(exporter, LokiExporter)
        self.assertEqual(exporter.get_name(), 'loki')
    
    def test_create_elasticsearch_exporter(self):
        """Test creating an ElasticSearch exporter"""
        config = {'url': 'http://elastic:9200'}
        exporter = ExporterFactory.create('elasticsearch', config)
        self.assertIsInstance(exporter, ElasticsearchExporter)
        self.assertEqual(exporter.get_name(), 'elasticsearch')
    
    def test_create_graylog_exporter(self):
        """Test creating a GrayLog exporter"""
        config = {'url': 'http://graylog:12201'}
        exporter = ExporterFactory.create('graylog', config)
        self.assertIsInstance(exporter, GraylogExporter)
        self.assertEqual(exporter.get_name(), 'graylog')
    
    def test_create_unknown_exporter(self):
        """Test creating an unknown exporter returns None"""
        config = {'url': 'http://unknown:9000'}
        exporter = ExporterFactory.create('unknown', config)
        self.assertIsNone(exporter)
    
    def test_list_exporters(self):
        """Test listing available exporters"""
        exporters = ExporterFactory.list_exporters()
        self.assertIn('loki', exporters)
        self.assertIn('elasticsearch', exporters)
        self.assertIn('graylog', exporters)


class TestLokiExporter(unittest.TestCase):
    """Test Loki exporter"""
    
    def setUp(self):
        """Set up test exporter"""
        self.config = {'url': 'http://loki:3100', 'timeout': 5}
        self.exporter = LokiExporter(self.config)
    
    @patch('exporters.loki.requests.post')
    def test_send_log_success(self, mock_post):
        """Test successful log sending"""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response
        
        log_entry = {
            'line': 'Test log line',
            'name': 'nginx',
            'subname': 'ACCESS',
            'filepath': '/var/log/nginx/access.log'
        }
        
        result = self.exporter.send_log(log_entry)
        self.assertTrue(result)
        mock_post.assert_called_once()
    
    @patch('exporters.loki.requests.post')
    def test_send_log_failure(self, mock_post):
        """Test failed log sending"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_post.return_value = mock_response
        
        log_entry = {
            'line': 'Test log line',
            'name': 'nginx',
            'subname': 'ACCESS',
            'filepath': '/var/log/nginx/access.log'
        }
        
        result = self.exporter.send_log(log_entry)
        self.assertFalse(result)
    
    @patch('exporters.loki.requests.post')
    def test_send_log_connection_error(self, mock_post):
        """Test connection error handling"""
        mock_post.side_effect = Exception('Connection refused')
        
        log_entry = {
            'line': 'Test log line',
            'name': 'nginx',
            'subname': 'ACCESS',
            'filepath': '/var/log/nginx/access.log'
        }
        
        result = self.exporter.send_log(log_entry)
        self.assertFalse(result)


class TestElasticsearchExporter(unittest.TestCase):
    """Test ElasticSearch exporter"""
    
    def setUp(self):
        """Set up test exporter"""
        self.config = {'url': 'http://elastic:9200', 'timeout': 5}
        self.exporter = ElasticsearchExporter(self.config)
    
    @patch('exporters.elasticsearch.requests.post')
    def test_send_log_success(self, mock_post):
        """Test successful log sending"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response
        
        log_entry = {
            'line': 'Test log line',
            'name': 'apache2',
            'subname': 'ERROR',
            'filepath': '/var/log/apache2/error.log'
        }
        
        result = self.exporter.send_log(log_entry)
        self.assertTrue(result)
        mock_post.assert_called_once()
    
    def test_index_prefix(self):
        """Test custom index prefix"""
        config = {'url': 'http://elastic:9200', 'index_prefix': 'custom-logs'}
        exporter = ElasticsearchExporter(config)
        self.assertEqual(exporter.index_prefix, 'custom-logs')


class TestGraylogExporter(unittest.TestCase):
    """Test GrayLog exporter"""
    
    def setUp(self):
        """Set up test exporter"""
        self.config = {'url': 'http://graylog:12201', 'timeout': 5}
        self.exporter = GraylogExporter(self.config)
    
    @patch('exporters.graylog.requests.post')
    def test_send_log_success(self, mock_post):
        """Test successful log sending"""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_post.return_value = mock_response
        
        log_entry = {
            'line': 'Test log line',
            'name': 'syslog',
            'subname': 'SYSTEM',
            'filepath': '/var/log/syslog'
        }
        
        result = self.exporter.send_log(log_entry)
        self.assertTrue(result)
        mock_post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
