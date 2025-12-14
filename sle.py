#!/usr/bin/env python3
"""
SLE - Simple Log Exporter
Main entry point
"""

import sys
import logging
import argparse
import threading
from pathlib import Path
from queue import Queue

from config_loader import ConfigLoader
from file_watcher import LogFileWatcher
from journald_watcher import JournaldWatcher
from exporters.factory import ExporterFactory


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SLE')


class SLE:
    """Simple Log Exporter main service"""
    
    def __init__(self, config_dir: str = "/etc/sle.d"):
        self.config_dir = config_dir
        self.watchers = []
        self.threads = []
        self.queue = Queue()
        self.running = False
        self.exporters = {}
        
    def start(self):
        """Start the service"""
        logger.info("Starting SLE (Simple Log Exporter)")
        
        # Load configurations
        config_loader = ConfigLoader(self.config_dir)
        configs = config_loader.load_configs()
        
        if not configs:
            logger.error("No valid configuration found. Stopping service.")
            return
        
        # Prepare exporters (support multiple backends per config)
        for config in configs:
            exporter_type = config.get('exporter_type', 'loki')
            exporter_configs = config.get('exporter_configs', [])
            
            # Handle each backend URL
            for exporter_config in exporter_configs:
                exporter_key = f"{exporter_type}:{exporter_config.get('url', '')}"
                
                if exporter_key not in self.exporters:
                    exporter = ExporterFactory.create(exporter_type, exporter_config)
                    if exporter:
                        self.exporters[exporter_key] = exporter
                        logger.info(f"Exporter configured: {exporter_type} -> {exporter_config.get('url', 'N/A')}")
        
        if not self.exporters:
            logger.error("No valid exporter configured. Stopping service.")
            return
        
        # Start watchers for each log file
        for config in configs:
            # Check if this is a journald config
            if config.get('journald_enabled'):
                # Start journald watcher
                watcher = JournaldWatcher(labels=config.get('journald_labels', {}))
                self.watchers.append(watcher)
                
                thread = threading.Thread(
                    target=watcher.start,
                    args=(self.queue,),
                    daemon=True
                )
                thread.start()
                self.threads.append(thread)
                continue
            
            # Regular file watchers
            for entry in config['log_entries']:
                watcher = LogFileWatcher(
                    filepath=entry['path_file'],
                    name=entry['name'],
                    subname=entry['subname'],
                    delimiter=entry['delimiter'],
                    labels=entry.get('labels', {}),
                    rate_limit=entry.get('rate_limit'),
                    buffer_size=entry.get('buffer_size')
                )
                self.watchers.append(watcher)
                
                # Create a thread for each watcher
                thread = threading.Thread(
                    target=watcher.start,
                    args=(self.queue,),
                    daemon=True
                )
                thread.start()
                self.threads.append(thread)
        
        logger.info(f"Watching {len(self.watchers)} source(s)")
        
        # Start queue processor
        self.running = True
        self._process_queue()
    
    def _process_queue(self):
        """Process logs from queue and send to exporters"""
        logger.info("Queue processing started")
        
        while self.running:
            try:
                if not self.queue.empty():
                    log_entry = self.queue.get(timeout=1)
                    
                    # Send to all exporters
                    for exporter in self.exporters.values():
                        exporter.send_log(log_entry)
                else:
                    import time
                    time.sleep(0.1)
                    
            except KeyboardInterrupt:
                logger.info("Interrupt detected, stopping service...")
                self.stop()
                break
            except Exception as e:
                logger.error(f"Error processing queue: {e}")
                import time
                time.sleep(1)
    
    def stop(self):
        """Stop the service"""
        logger.info("Stopping SLE...")
        self.running = False
        
        for watcher in self.watchers:
            watcher.stop()
        
        logger.info("SLE stopped")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='SLE - Simple Log Exporter: Export logs to Grafana Loki and other backends'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start service with fixed config directory
    sle = SLE(config_dir='/etc/sle.d')
    
    try:
        sle.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sle.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
