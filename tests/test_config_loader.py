"""
Unit tests for SLE configuration loader
"""

import unittest
import tempfile
import os
import json
import yaml
from pathlib import Path

from config_loader import ConfigLoader


class TestConfigLoader(unittest.TestCase):
    """Test configuration loading and validation"""
    
    def setUp(self):
        """Create a temporary directory for test configs"""
        self.test_dir = tempfile.mkdtemp()
        self.loader = ConfigLoader(self.test_dir)
    
    def tearDown(self):
        """Clean up test directory"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_load_valid_loki_json(self):
        """Test loading a valid Loki JSON configuration"""
        config = {
            "LOKI_IP": "10.10.10.10:3100",
            "nginx": {
                "ACCESS": {
                    "path_file": "/var/log/nginx/access.log"
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]['exporter_type'], 'loki')
        self.assertEqual(len(configs[0]['log_entries']), 1)
        self.assertEqual(configs[0]['log_entries'][0]['name'], 'nginx')
        self.assertEqual(configs[0]['log_entries'][0]['subname'], 'ACCESS')
    
    def test_load_valid_elastic_yaml(self):
        """Test loading a valid ElasticSearch YAML configuration"""
        config = {
            "ELASTIC_IP": "http://elasticsearch:9200",
            "apache2": {
                "ACCESS": {
                    "path_file": "/var/log/apache2/access.log",
                    "delimiter": "\\n"
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.yaml")
        with open(config_file, 'w') as f:
            yaml.dump(config, f)
        
        configs = self.loader.load_configs()
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]['exporter_type'], 'elastic')
        self.assertIn('http://', configs[0]['exporter_configs'][0]['url'])
    
    def test_load_multiple_configs(self):
        """Test loading multiple configuration files"""
        # Create first config (JSON)
        config1 = {
            "LOKI_IP": "loki:3100",
            "app1": {
                "LOGS": {
                    "path_file": "/var/log/app1.log"
                }
            }
        }
        with open(os.path.join(self.test_dir, "app1.json"), 'w') as f:
            json.dump(config1, f)
        
        # Create second config (YAML)
        config2 = {
            "GRAYLOG_IP": "graylog:12201",
            "app2": {
                "LOGS": {
                    "path_file": "/var/log/app2.log"
                }
            }
        }
        with open(os.path.join(self.test_dir, "app2.yml"), 'w') as f:
            yaml.dump(config2, f)
        
        configs = self.loader.load_configs()
        self.assertEqual(len(configs), 2)
    
    def test_missing_path_file(self):
        """Test configuration with missing path_file"""
        config = {
            "LOKI_IP": "loki:3100",
            "nginx": {
                "ACCESS": {
                    "delimiter": "\\n"
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "invalid.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        # Should have 0 valid configs (path_file is mandatory)
        self.assertEqual(len(configs), 0)
    
    def test_invalid_json(self):
        """Test handling of invalid JSON file"""
        config_file = os.path.join(self.test_dir, "invalid.json")
        with open(config_file, 'w') as f:
            f.write("{ invalid json }")
        
        configs = self.loader.load_configs()
        self.assertEqual(len(configs), 0)
    
    def test_http_protocol_added(self):
        """Test that http:// is added if missing"""
        config = {
            "LOKI_IP": "10.10.10.10:3100",
            "test": {
                "LOG": {
                    "path_file": "/var/log/test.log"
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        self.assertTrue(configs[0]['exporter_configs'][0]['url'].startswith('http://'))
    
    def test_delimiter_default(self):
        """Test default delimiter is newline"""
        config = {
            "LOKI_IP": "loki:3100",
            "test": {
                "LOG": {
                    "path_file": "/var/log/test.log"
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        self.assertEqual(configs[0]['log_entries'][0]['delimiter'], '\n')
    
    def test_custom_delimiter(self):
        """Test custom delimiter is preserved"""
        config = {
            "LOKI_IP": "loki:3100",
            "test": {
                "LOG": {
                    "path_file": "/var/log/test.log",
                    "delimiter": "\\r\\n"
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        self.assertEqual(configs[0]['log_entries'][0]['delimiter'], '\\r\\n')
    
    def test_backend_type_detection(self):
        """Test backend type is correctly detected from *_IP field"""
        backends = [
            ("LOKI_IP", "loki"),
            ("ELASTIC_IP", "elastic"),
            ("ELASTICSEARCH_IP", "elasticsearch"),
            ("GRAYLOG_IP", "graylog"),
            ("OPENSEARCH_IP", "opensearch"),
        ]
        
        for backend_field, expected_type in backends:
            config = {
                backend_field: "http://backend:9000",
                "test": {
                    "LOG": {
                        "path_file": "/var/log/test.log"
                    }
                }
            }
            
            config_file = os.path.join(self.test_dir, f"test_{backend_field}.json")
            with open(config_file, 'w') as f:
                json.dump(config, f)
        
        configs = self.loader.load_configs()
        self.assertEqual(len(configs), len(backends))
        
        backend_types = [c['exporter_type'] for c in configs]
        for _, expected_type in backends:
            self.assertIn(expected_type, backend_types)
    
    def test_labels_parsing(self):
        """Test optional labels are correctly parsed"""
        config = {
            "LOKI_IP": "loki:3100",
            "nginx": {
                "ACCESS": {
                    "path_file": "/var/log/nginx/access.log",
                    "labels": {
                        "environment": "production",
                        "datacenter": "eu-west-1",
                        "team": "ops"
                    }
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        self.assertEqual(len(configs), 1)
        
        log_entry = configs[0]['log_entries'][0]
        self.assertIn('labels', log_entry)
        self.assertEqual(log_entry['labels']['environment'], 'production')
        self.assertEqual(log_entry['labels']['datacenter'], 'eu-west-1')
        self.assertEqual(log_entry['labels']['team'], 'ops')
    
    def test_labels_empty_default(self):
        """Test labels default to empty dict"""
        config = {
            "LOKI_IP": "loki:3100",
            "test": {
                "LOG": {
                    "path_file": "/var/log/test.log"
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        log_entry = configs[0]['log_entries'][0]
        self.assertEqual(log_entry['labels'], {})
    
    def test_labels_invalid_type(self):
        """Test invalid labels (non-dict) are ignored"""
        config = {
            "LOKI_IP": "loki:3100",
            "test": {
                "LOG": {
                    "path_file": "/var/log/test.log",
                    "labels": "invalid"
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        log_entry = configs[0]['log_entries'][0]
        self.assertEqual(log_entry['labels'], {})
    
    def test_rate_limit_parsing(self):
        """Test optional rate_limit is correctly parsed"""
        config = {
            "LOKI_IP": "loki:3100",
            "test": {
                "LOG": {
                    "path_file": "/var/log/test.log",
                    "rate_limit": 1000
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        log_entry = configs[0]['log_entries'][0]
        self.assertEqual(log_entry['rate_limit'], 1000)
    
    def test_rate_limit_float(self):
        """Test rate_limit supports float values"""
        config = {
            "LOKI_IP": "loki:3100",
            "test": {
                "LOG": {
                    "path_file": "/var/log/test.log",
                    "rate_limit": 500.5
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        log_entry = configs[0]['log_entries'][0]
        self.assertEqual(log_entry['rate_limit'], 500.5)
    
    def test_rate_limit_invalid(self):
        """Test invalid rate_limit is ignored"""
        config = {
            "LOKI_IP": "loki:3100",
            "test": {
                "LOG": {
                    "path_file": "/var/log/test.log",
                    "rate_limit": -100
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        log_entry = configs[0]['log_entries'][0]
        self.assertIsNone(log_entry['rate_limit'])
    
    def test_buffer_size_parsing(self):
        """Test optional buffer_size is correctly parsed"""
        config = {
            "LOKI_IP": "loki:3100",
            "test": {
                "LOG": {
                    "path_file": "/var/log/test.log",
                    "buffer_size": 100
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        log_entry = configs[0]['log_entries'][0]
        self.assertEqual(log_entry['buffer_size'], 100)
    
    def test_buffer_size_invalid(self):
        """Test invalid buffer_size is ignored"""
        config = {
            "LOKI_IP": "loki:3100",
            "test": {
                "LOG": {
                    "path_file": "/var/log/test.log",
                    "buffer_size": -50
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        log_entry = configs[0]['log_entries'][0]
        self.assertIsNone(log_entry['buffer_size'])
    
    def test_all_optional_fields(self):
        """Test all optional fields together"""
        config = {
            "LOKI_IP": "loki:3100",
            "nginx": {
                "ACCESS": {
                    "path_file": "/var/log/nginx/access.log",
                    "delimiter": "||",
                    "labels": {
                        "env": "prod"
                    },
                    "rate_limit": 1000,
                    "buffer_size": 50
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        log_entry = configs[0]['log_entries'][0]
        
        self.assertEqual(log_entry['delimiter'], '||')
        self.assertEqual(log_entry['labels']['env'], 'prod')
        self.assertEqual(log_entry['rate_limit'], 1000)
        self.assertEqual(log_entry['buffer_size'], 50)
    
    def test_multiple_backend_urls(self):
        """Test multiple backend URLs for high availability"""
        config = {
            "LOKI_IP": [
                "loki-1:3100",
                "loki-2:3100",
                "loki-3:3100"
            ],
            "test": {
                "LOG": {
                    "path_file": "/var/log/test.log"
                }
            }
        }
        
        config_file = os.path.join(self.test_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        configs = self.loader.load_configs()
        self.assertEqual(len(configs), 1)
        
        # Should have 3 backend configurations
        self.assertEqual(len(configs[0]['exporter_configs']), 3)
        
        # Check all URLs are present with http://
        urls = [c['url'] for c in configs[0]['exporter_configs']]
        self.assertIn('http://loki-1:3100', urls)
        self.assertIn('http://loki-2:3100', urls)
        self.assertIn('http://loki-3:3100', urls)
    
    def test_mixed_single_and_multiple_backends(self):
        """Test mixing single and multiple backend configs"""
        # Config with multiple backends
        config1 = {
            "LOKI_IP": ["loki-1:3100", "loki-2:3100"],
            "app1": {
                "LOGS": {
                    "path_file": "/var/log/app1.log"
                }
            }
        }
        with open(os.path.join(self.test_dir, "app1.json"), 'w') as f:
            json.dump(config1, f)
        
        # Config with single backend
        config2 = {
            "ELASTIC_IP": "elasticsearch:9200",
            "app2": {
                "LOGS": {
                    "path_file": "/var/log/app2.log"
                }
            }
        }
        with open(os.path.join(self.test_dir, "app2.json"), 'w') as f:
            json.dump(config2, f)
        
        configs = self.loader.load_configs()
        self.assertEqual(len(configs), 2)
        
        # Find configs by backend count
        multi_backend = [c for c in configs if len(c['exporter_configs']) > 1][0]
        single_backend = [c for c in configs if len(c['exporter_configs']) == 1][0]
        
        self.assertEqual(len(multi_backend['exporter_configs']), 2)
        self.assertEqual(len(single_backend['exporter_configs']), 1)


if __name__ == '__main__':
    unittest.main()
