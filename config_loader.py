"""
Configuration loader for SLE
Handles JSON and YAML configuration files
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any


logger = logging.getLogger('SLE.ConfigLoader')


class ConfigLoader:
    """Load and validate configuration files"""
    
    def __init__(self, config_dir: str = "/etc/sle.d"):
        self.config_dir = config_dir
        
    def load_configs(self) -> List[Dict[str, Any]]:
        """Load all valid configuration files"""
        configs = []
        journald_enabled = False  # Default: journald disabled unless default.json exists
        journald_labels = {}
        default_file_found = False
        
        if not os.path.exists(self.config_dir):
            logger.error(f"Configuration directory does not exist: {self.config_dir}")
            return configs
        
        # List all configuration files
        config_files = []
        for ext in ['*.json', '*.yaml', '*.yml']:
            config_files.extend(Path(self.config_dir).glob(ext))
        
        if not config_files:
            logger.warning(f"No configuration files found in {self.config_dir}")
            return configs
        
        logger.info(f"Found {len(config_files)} configuration file(s)")
        
        # First pass: check default.json or default.yml for JOURNALCTL setting
        for config_file in config_files:
            if config_file.stem == 'default':
                default_file_found = True
                try:
                    config = self._load_file(config_file)
                    if config:
                        # Check if JOURNALCTL is explicitly set
                        if 'JOURNALCTL' in config:
                            journalctl_value = config['JOURNALCTL']
                            if isinstance(journalctl_value, str):
                                journald_enabled = journalctl_value.lower() in ['on', 'yes', 'true', '1']
                            elif isinstance(journalctl_value, bool):
                                journald_enabled = journalctl_value
                            
                            logger.info(f"Journald monitoring: {'enabled' if journald_enabled else 'disabled'}")
                        else:
                            # If default.json exists but no JOURNALCTL key, disabled by default
                            journald_enabled = False
                            logger.info("default.json found without JOURNALCTL key - journald monitoring disabled")
                        
                        # Extract labels for journald if present
                        if 'JOURNALCTL_LABELS' in config and isinstance(config['JOURNALCTL_LABELS'], dict):
                            journald_labels = config['JOURNALCTL_LABELS']
                except Exception as e:
                    logger.error(f"Error loading default config {config_file}: {e}")
        
        if not default_file_found:
            logger.info("No default.json or default.yml found - journald monitoring disabled")
        
        # Second pass: load all configs
        for config_file in config_files:
            try:
                config = self._load_file(config_file)
                if config:
                    validated_config = self._validate_config(config, str(config_file))
                    if validated_config:
                        configs.append(validated_config)
            except Exception as e:
                logger.error(f"Error loading {config_file}: {e}")
                # Continue with other files
                continue
        
        # Add journald config if enabled
        if journald_enabled and configs:
            # Use the first backend found
            first_backend = configs[0]['exporter_type']
            first_backend_configs = configs[0]['exporter_configs']
            
            configs.append({
                'exporter_type': first_backend,
                'exporter_configs': first_backend_configs,
                'log_entries': [],
                'source': 'journald',
                'journald_enabled': True,
                'journald_labels': journald_labels
            })
            logger.info(f"Journald monitoring enabled, using {first_backend} backend with {len(first_backend_configs)} destination(s)")
        
        return configs
    
    def _load_file(self, filepath: Path) -> Optional[Dict]:
        """Load a JSON or YAML file"""
        try:
            with open(filepath, 'r') as f:
                if filepath.suffix == '.json':
                    return json.load(f)
                else:  # .yaml or .yml
                    return yaml.safe_load(f)
        except json.JSONDecodeError as e:
            logger.error(f"JSON error in {filepath}: {e}")
            return None
        except yaml.YAMLError as e:
            logger.error(f"YAML error in {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
            return None
    
    def _validate_config(self, config: Dict, source: str) -> Optional[Dict]:
        """Validate and normalize a configuration"""
        if not isinstance(config, dict):
            logger.error(f"Invalid configuration in {source}: must be an object")
            return None
        
        # Detect backend configuration (any field ending with _IP)
        exporter_type = None
        exporter_configs = []  # Support multiple backends
        backend_key = None
        
        for key in config.keys():
            if key.endswith('_IP'):
                backend_key = key
                backend_value = config[key]
                
                if not backend_value:
                    logger.error(f"Invalid configuration in {source}: {key} is empty")
                    return None
                
                # Extract backend type from key (e.g., LOKI_IP -> loki)
                exporter_type = key[:-3].lower()  # Remove _IP suffix
                
                # Support both single value and list
                backend_urls = []
                if isinstance(backend_value, list):
                    backend_urls = backend_value
                else:
                    backend_urls = [backend_value]
                
                # Process each URL
                for url in backend_urls:
                    if not url:
                        continue
                    # Add http:// if no scheme
                    if not url.startswith(('http://', 'https://')):
                        url = f"http://{url}"
                    exporter_configs.append({'url': url})
                
                break
        
        # If no *_IP found, log a warning but continue (for future compatibility)
        if not exporter_type:
            logger.warning(f"No backend configuration (*_IP) found in {source}, defaulting to loki")
            exporter_type = 'loki'
            exporter_configs = [{'url': 'http://localhost:3100'}]
        
        # Parse log entries
        log_entries = []
        for name, subconfigs in config.items():
            # Skip backend configuration keys
            if name.endswith('_IP'):
                continue
            
            if not isinstance(subconfigs, dict):
                logger.warning(f"Entry '{name}' ignored in {source}: must be an object")
                continue
            
            for subname, settings in subconfigs.items():
                if not isinstance(settings, dict):
                    logger.warning(f"Entry '{name}.{subname}' ignored in {source}: must be an object")
                    continue
                
                # Check required path_file
                if 'path_file' not in settings:
                    logger.warning(f"Entry '{name}.{subname}' ignored in {source}: path_file is missing")
                    continue
                
                path_file = settings['path_file']
                if not path_file:
                    logger.warning(f"Entry '{name}.{subname}' ignored in {source}: path_file is empty")
                    continue
                
                # Optional delimiter (default: newline)
                delimiter = settings.get('delimiter', '\n')
                
                # Optional labels (must be a dict)
                labels = settings.get('labels', {})
                if not isinstance(labels, dict):
                    logger.warning(f"Entry '{name}.{subname}' labels must be a dict, ignoring")
                    labels = {}
                
                # Optional rate_limit (logs per second)
                rate_limit = settings.get('rate_limit')
                if rate_limit is not None and (not isinstance(rate_limit, (int, float)) or rate_limit <= 0):
                    logger.warning(f"Entry '{name}.{subname}' invalid rate_limit: {rate_limit}, ignoring")
                    rate_limit = None
                
                # Optional buffer_size (batch size)
                buffer_size = settings.get('buffer_size')
                if buffer_size is not None and (not isinstance(buffer_size, int) or buffer_size <= 0):
                    logger.warning(f"Entry '{name}.{subname}' invalid buffer_size: {buffer_size}, ignoring")
                    buffer_size = None
                
                log_entries.append({
                    'name': name,
                    'subname': subname,
                    'path_file': path_file,
                    'delimiter': delimiter,
                    'labels': labels,
                    'rate_limit': rate_limit,
                    'buffer_size': buffer_size
                })
        
        if not log_entries:
            logger.warning(f"No valid log entries found in {source}")
            return None
        
        return {
            'exporter_type': exporter_type,
            'exporter_configs': exporter_configs,  # List of backend configs
            'log_entries': log_entries,
            'source': source
        }
