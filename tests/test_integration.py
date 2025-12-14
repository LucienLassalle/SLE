"""
Integration tests for SLE
Tests the complete configuration loading and validation flow
"""

import unittest
import tempfile
import os
import json
import yaml
import shutil

from config_loader import ConfigLoader
from exporters.factory import ExporterFactory


class TestIntegration(unittest.TestCase):
    """Integration tests for SLE"""
    
    def setUp(self):
        """Create a temporary directory for test configs"""
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test directory"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_complete_workflow_json(self):
        """Test complete workflow with JSON configuration"""
        # Create a valid JSON config
        config = {
            "LOKI_IP": "10.10.10.10:3100",
            "nginx": {
                "ACCESS": {
                    "path_file": "/var/log/nginx/access.log",
                    "delimiter": "\n"
                },
                "ERROR": {
                    "path_file": "/var/log/nginx/error.log"
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "nginx.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        # Load configuration
        loader = ConfigLoader(self.test_dir)
        configs = loader.load_configs()
        
        # Verify loading
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]['exporter_type'], 'loki')
        self.assertEqual(len(configs[0]['log_entries']), 2)
        
        # Create exporter
        exporter = ExporterFactory.create(
            configs[0]['exporter_type'],
            configs[0]['exporter_configs'][0]
        )
        
        self.assertIsNotNone(exporter)
        self.assertEqual(exporter.get_name(), 'loki')
    
    def test_complete_workflow_yaml(self):
        """Test complete workflow with YAML configuration"""
        # Create a valid YAML config
        config = {
            "ELASTIC_IP": "http://elasticsearch:9200",
            "apache2": {
                "ACCESS": {
                    "path_file": "/var/log/apache2/access.log"
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "apache.yaml")
        with open(config_file, 'w') as f:
            yaml.dump(config, f)
        
        # Load configuration
        loader = ConfigLoader(self.test_dir)
        configs = loader.load_configs()
        
        # Verify loading
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]['exporter_type'], 'elastic')
        
        # Create exporter
        exporter = ExporterFactory.create(
            configs[0]['exporter_type'],
            configs[0]['exporter_configs'][0]
        )
        
        self.assertIsNotNone(exporter)
        self.assertEqual(exporter.get_name(), 'elasticsearch')
    
    def test_mixed_formats(self):
        """Test loading multiple configs with different formats"""
        # Create JSON config
        json_config = {
            "LOKI_IP": "loki:3100",
            "app1": {
                "LOGS": {
                    "path_file": "/var/log/app1.log"
                }
            }
        }
        with open(os.path.join(self.test_dir, "app1.json"), 'w') as f:
            json.dump(json_config, f)
        
        # Create YAML config
        yaml_config = {
            "GRAYLOG_IP": "graylog:12201",
            "app2": {
                "LOGS": {
                    "path_file": "/var/log/app2.log"
                }
            }
        }
        with open(os.path.join(self.test_dir, "app2.yml"), 'w') as f:
            yaml.dump(yaml_config, f)
        
        # Load all configs
        loader = ConfigLoader(self.test_dir)
        configs = loader.load_configs()
        
        # Verify both loaded
        self.assertEqual(len(configs), 2)
        
        # Verify different backend types
        backend_types = [c['exporter_type'] for c in configs]
        self.assertIn('loki', backend_types)
        self.assertIn('graylog', backend_types)
    
    def test_invalid_config_doesnt_break_others(self):
        """Test that one invalid config doesn't prevent loading others"""
        # Create a valid config
        valid_config = {
            "LOKI_IP": "loki:3100",
            "valid_app": {
                "LOGS": {
                    "path_file": "/var/log/valid.log"
                }
            }
        }
        with open(os.path.join(self.test_dir, "valid.json"), 'w') as f:
            json.dump(valid_config, f)
        
        # Create an invalid config (no path_file)
        invalid_config = {
            "LOKI_IP": "loki:3100",
            "invalid_app": {
                "LOGS": {
                    "delimiter": "\n"
                }
            }
        }
        with open(os.path.join(self.test_dir, "invalid.json"), 'w') as f:
            json.dump(invalid_config, f)
        
        # Create a malformed JSON
        with open(os.path.join(self.test_dir, "malformed.json"), 'w') as f:
            f.write("{ invalid json }")
        
        # Load configs
        loader = ConfigLoader(self.test_dir)
        configs = loader.load_configs()
        
        # Should have 1 valid config (the first one)
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]['log_entries'][0]['name'], 'valid_app')
    
    def test_all_supported_backends(self):
        """Test that all supported backends can be loaded"""
        backends = [
            "LOKI_IP",
            "ELASTIC_IP",
            "ELASTICSEARCH_IP",
            "OPENSEARCH_IP",
            "GRAYLOG_IP",
            "VICTORIALOGS_IP",
            "CLICKHOUSE_IP",
            "FLUENTBIT_IP",
            "KAFKA_IP",
        ]
        
        for i, backend in enumerate(backends):
            config = {
                backend: f"http://backend{i}:9000",
                f"app{i}": {
                    "LOGS": {
                        "path_file": f"/var/log/app{i}.log"
                    }
                }
            }
            with open(os.path.join(self.test_dir, f"config{i}.json"), 'w') as f:
                json.dump(config, f)
        
        # Load all configs
        loader = ConfigLoader(self.test_dir)
        configs = loader.load_configs()
        
        # Verify all loaded
        self.assertEqual(len(configs), len(backends))


if __name__ == '__main__':
    unittest.main()
