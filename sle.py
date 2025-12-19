#!/usr/bin/env python3
"""
SLE - Simple Log Exporter
Main entry point
"""

import sys
import logging
import argparse
import threading
import time
from pathlib import Path
from queue import Queue
from typing import Dict, Any

from config_loader import ConfigLoader
from file_watcher import LogFileWatcher
from journald_watcher import JournaldWatcher
from exporters.factory import ExporterFactory
from disk_buffer import DiskBuffer


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
        self.rate_limiters = {}  # Track rate limits per source
        self.buffers = {}  # Track log buffers per source
        self.disk_buffers = {}  # Track disk buffers per source
        self.auto_reload_interval = 0
        self.last_reload_time = 0
        self.active_files = set()  # Track currently monitored files
        self.queue_size_limit = None  # Queue size limit (None = default 5000 before clear)
        self.queue_warning_thresholds = set()  # Track which warnings were already logged
        self.last_queue_check = 0  # Last time we checked queue size
        
    def start(self):
        """Start the service"""
        logger.info("Starting SLE (Simple Log Exporter)")
        
        # Initial load
        self._load_and_start_watchers()
        
        # Start queue processor
        self.running = True
        
        # Start auto-reload thread if enabled
        if self.auto_reload_interval > 0:
            reload_thread = threading.Thread(
                target=self._auto_reload_worker,
                daemon=True
            )
            reload_thread.start()
            self.threads.append(reload_thread)
        
        # Replay any buffered logs from disk
        self._replay_disk_buffers()
        
        self._process_queue()
    
    def _load_and_start_watchers(self):
        """Load configurations and start watchers"""
        # Load configurations
        config_loader = ConfigLoader(self.config_dir)
        configs = config_loader.load_configs()
        
        if not configs:
            logger.error("No valid configuration found.")
            return
        
        # Get auto-reload interval from configs
        if configs:
            self.auto_reload_interval = configs[0].get('auto_reload_interval', 0)
            self.queue_size_limit = configs[0].get('queue_size')
            if self.queue_size_limit:
                logger.info(f"Queue size limit configured: {self.queue_size_limit} logs")
            else:
                logger.info("Queue size: unlimited (will clear at 5000 with CRITICAL)")
        
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
            logger.error("No valid exporter configured.")
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
                file_path = entry['path_file']
                
                # Skip if already monitored
                if file_path in self.active_files:
                    continue
                
                self.active_files.add(file_path)
                
                watcher = LogFileWatcher(
                    filepath=file_path,
                    name=entry['name'],
                    subname=entry['subname'],
                    delimiter=entry['delimiter'],
                    labels=entry.get('labels', {}),
                    rate_limit=entry.get('rate_limit'),
                    buffer_size=entry.get('buffer_size')
                )
                self.watchers.append(watcher)
                
                # Initialize rate limiter if specified
                source_key = f"{entry['name']}:{entry['subname']}:{file_path}"
                if entry.get('rate_limit'):
                    self.rate_limiters[source_key] = {
                        'max_rate': entry['rate_limit'],
                        'tokens': entry['rate_limit'],  # Start with full bucket
                        'last_update': time.time()
                    }
                
                # Initialize buffer if specified
                if entry.get('buffer_size'):
                    self.buffers[source_key] = {
                        'max_size': entry['buffer_size'],
                        'logs': []
                    }
                
                # Initialize disk buffer if specified
                if entry.get('disk_buffer') == 'DISK':
                    # Sanitize name and subname to prevent path traversal
                    safe_name = entry['name'].replace('..', '').replace('/', '_')
                    safe_subname = entry['subname'].replace('..', '').replace('/', '_')
                    buffer_dir = f"/var/lib/sle/buffer/{safe_name}/{safe_subname}"
                    self.disk_buffers[source_key] = DiskBuffer(buffer_dir)
                    logger.info(f"Disk buffer enabled for {source_key}")
                
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
                # Check queue size periodically
                current_time = time.time()
                if current_time - self.last_queue_check >= 1:  # Check every second
                    self._check_queue_size()
                    self.last_queue_check = current_time
                
                if not self.queue.empty():
                    log_entry = self.queue.get(timeout=1)
                    
                    # Generate source key for rate limiting and buffering
                    source_key = f"{log_entry['name']}:{log_entry['subname']}:{log_entry['filepath']}"
                    
                    # Check rate limit
                    if source_key in self.rate_limiters:
                        if not self._check_rate_limit(source_key):
                            # Rate limit exceeded, check disk buffer strategy
                            if source_key in self.disk_buffers:
                                # Save to disk instead of dropping
                                self.disk_buffers[source_key].write(log_entry)
                                logger.debug(f"Rate limit exceeded for {source_key}, saved to disk buffer")
                            else:
                                logger.debug(f"Rate limit exceeded for {source_key}, dropping log")
                            continue
                    
                    # Check if buffering is enabled
                    if source_key in self.buffers:
                        # Add to buffer (batch sending)
                        self.buffers[source_key]['logs'].append(log_entry)
                        
                        # Send batch if buffer is full
                        if len(self.buffers[source_key]['logs']) >= self.buffers[source_key]['max_size']:
                            self._flush_buffer(source_key)
                    else:
                        # No buffering, send immediately
                        success = self._send_log_to_exporters(log_entry)
                        
                        # If sending failed and disk buffer is enabled, save to disk
                        if not success and source_key in self.disk_buffers:
                            self.disk_buffers[source_key].write(log_entry)
                            logger.debug(f"Failed to send log from {source_key}, saved to disk buffer")
                else:
                    # Flush all partial buffers periodically
                    self._flush_all_buffers()
                    time.sleep(0.1)
                    
            except KeyboardInterrupt:
                logger.info("Interrupt detected, stopping service...")
                self.stop()
                break
            except Exception as e:
                logger.error(f"Error processing queue: {e}")
                time.sleep(1)
    
    def _check_rate_limit(self, source_key: str) -> bool:
        """Check if log can be sent based on rate limit (token bucket algorithm)"""
        limiter = self.rate_limiters[source_key]
        now = time.time()
        elapsed = now - limiter['last_update']
        
        # Refill tokens based on elapsed time
        limiter['tokens'] = min(
            limiter['max_rate'],
            limiter['tokens'] + elapsed * limiter['max_rate']
        )
        limiter['last_update'] = now
        
        # Check if we have tokens available
        if limiter['tokens'] >= 1.0:
            limiter['tokens'] -= 1.0
            return True
        return False
    
    def _flush_buffer(self, source_key: str):
        """Flush buffered logs for a specific source"""
        if source_key not in self.buffers or not self.buffers[source_key]['logs']:
            return
        
        logs = self.buffers[source_key]['logs']
        logger.debug(f"Flushing {len(logs)} buffered logs from {source_key}")
        
        # Send all buffered logs
        failed_logs = []
        for log_entry in logs:
            success = self._send_log_to_exporters(log_entry)
            
            # If sending failed and disk buffer is enabled, save to disk
            if not success and source_key in self.disk_buffers:
                self.disk_buffers[source_key].write(log_entry)
                logger.debug(f"Failed to send buffered log from {source_key}, saved to disk")
            elif not success:
                failed_logs.append(log_entry)
        
        if failed_logs:
            logger.warning(f"Failed to send {len(failed_logs)} logs from {source_key} buffer (no disk buffer configured)")
        
        # Clear buffer
        self.buffers[source_key]['logs'] = []
    
    def _flush_all_buffers(self):
        """Flush all partial buffers"""
        for source_key in list(self.buffers.keys()):
            if self.buffers[source_key]['logs']:
                self._flush_buffer(source_key)
    
    def _check_queue_size(self):
        """Check queue size and log warnings/clear if needed"""
        try:
            qsize = self.queue.qsize()
        except NotImplementedError:
            # Some Queue implementations don't support qsize()
            return
        
        # Determine effective limit
        effective_limit = self.queue_size_limit if self.queue_size_limit else 5000
        
        # Calculate warning thresholds (every 20%)
        threshold_20 = int(effective_limit * 0.2)
        threshold_40 = int(effective_limit * 0.4)
        threshold_60 = int(effective_limit * 0.6)
        threshold_80 = int(effective_limit * 0.8)
        
        # Log warnings at thresholds
        if qsize >= threshold_80 and 80 not in self.queue_warning_thresholds:
            logger.warning(f"Queue at 80%: {qsize}/{effective_limit} logs")
            self.queue_warning_thresholds.add(80)
        elif qsize >= threshold_60 and 60 not in self.queue_warning_thresholds:
            logger.warning(f"Queue at 60%: {qsize}/{effective_limit} logs")
            self.queue_warning_thresholds.add(60)
        elif qsize >= threshold_40 and 40 not in self.queue_warning_thresholds:
            logger.warning(f"Queue at 40%: {qsize}/{effective_limit} logs")
            self.queue_warning_thresholds.add(40)
        elif qsize >= threshold_20 and 20 not in self.queue_warning_thresholds:
            logger.warning(f"Queue at 20%: {qsize}/{effective_limit} logs")
            self.queue_warning_thresholds.add(20)
        
        # Reset thresholds when queue size decreases
        if qsize < threshold_20:
            self.queue_warning_thresholds.clear()
        elif qsize < threshold_40:
            self.queue_warning_thresholds.discard(20)
        elif qsize < threshold_60:
            self.queue_warning_thresholds.discard(20)
            self.queue_warning_thresholds.discard(40)
        elif qsize < threshold_80:
            self.queue_warning_thresholds.discard(20)
            self.queue_warning_thresholds.discard(40)
            self.queue_warning_thresholds.discard(60)
        
        # Handle queue limit reached
        if qsize >= effective_limit:
            if self.queue_size_limit:
                # User-defined limit with disk_buffer
                logger.critical(f"Queue limit reached: {qsize}/{effective_limit} logs")
                self._handle_queue_overflow()
            else:
                # Default: clear queue at 5000
                logger.critical(f"Queue limit reached (default): {qsize}/5000 logs - CLEARING QUEUE")
                self._clear_queue()
    
    def _handle_queue_overflow(self):
        """Handle queue overflow when user-defined limit is reached"""
        # Try to save to disk buffers if configured
        saved_count = 0
        dropped_count = 0
        
        # Drain queue and save to disk buffers
        while not self.queue.empty():
            try:
                log_entry = self.queue.get_nowait()
                source_key = f"{log_entry['name']}:{log_entry['subname']}:{log_entry['filepath']}"
                
                # Check if disk buffer is enabled for this source
                if source_key in self.disk_buffers:
                    self.disk_buffers[source_key].write(log_entry)
                    saved_count += 1
                else:
                    dropped_count += 1
            except:
                break
        
        if saved_count > 0:
            logger.warning(f"Queue overflow: saved {saved_count} logs to disk, dropped {dropped_count} logs")
        else:
            logger.critical(f"Queue overflow: dropped {dropped_count} logs (no disk buffer configured)")
        
        # Reset warning thresholds
        self.queue_warning_thresholds.clear()
    
    def _clear_queue(self):
        """Clear the entire queue (used when no limit is set)"""
        cleared_count = 0
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                cleared_count += 1
            except:
                break
        
        logger.critical(f"Cleared {cleared_count} logs from queue")
        self.queue_warning_thresholds.clear()
    
    def _send_log_to_exporters(self, log_entry: Dict[str, Any]) -> bool:
        """Send log to all exporters, return True if at least one succeeded"""
        success = False
        for exporter in self.exporters.values():
            try:
                exporter.send_log(log_entry)
                success = True
            except Exception as e:
                logger.error(f"Failed to send log to exporter: {e}")
        return success
    
    def _replay_disk_buffers(self):
        """Replay logs from disk buffers at startup"""
        for source_key, disk_buffer in self.disk_buffers.items():
            pending_files = disk_buffer.get_pending_files()
            if pending_files:
                logger.info(f"Found {len(pending_files)} buffered logs for {source_key}, replaying...")
                
                for file_path in pending_files:
                    log_entry = disk_buffer.read_log_entry(file_path)
                    if log_entry:
                        processing_path = disk_buffer.move_to_processing(file_path)
                        if processing_path:
                            success = self._send_log_to_exporters(log_entry)
                            if success:
                                disk_buffer.delete_processed(processing_path)
                            else:
                                disk_buffer.move_back_to_pending(processing_path)
    
    def _auto_reload_worker(self):
        """Worker thread for auto-reloading configurations"""
        logger.info(f"Auto-reload worker started (interval: {self.auto_reload_interval}s)")
        
        while self.running:
            time.sleep(self.auto_reload_interval)
            
            try:
                logger.info("Auto-reload: checking for new files matching patterns...")
                
                # Load fresh configurations
                config_loader = ConfigLoader(self.config_dir)
                configs = config_loader.load_configs()
                
                new_files_found = False
                for config in configs:
                    if config.get('journald_enabled'):
                        continue
                    
                    for entry in config['log_entries']:
                        file_path = entry['path_file']
                        
                        # Check if this is a new file
                        if file_path not in self.active_files:
                            new_files_found = True
                            self.active_files.add(file_path)
                            
                            logger.info(f"Auto-reload: new file detected: {file_path}")
                            
                            # Start watcher for new file
                            watcher = LogFileWatcher(
                                filepath=file_path,
                                name=entry['name'],
                                subname=entry['subname'],
                                delimiter=entry['delimiter'],
                                labels=entry.get('labels', {}),
                                rate_limit=entry.get('rate_limit'),
                                buffer_size=entry.get('buffer_size')
                            )
                            self.watchers.append(watcher)
                            
                            # Initialize rate limiter if specified
                            source_key = f"{entry['name']}:{entry['subname']}:{file_path}"
                            if entry.get('rate_limit'):
                                self.rate_limiters[source_key] = {
                                    'max_rate': entry['rate_limit'],
                                    'tokens': entry['rate_limit'],
                                    'last_update': time.time()
                                }
                            
                            # Initialize buffer if specified
                            if entry.get('buffer_size'):
                                self.buffers[source_key] = {
                                    'max_size': entry['buffer_size'],
                                    'logs': []
                                }
                            
                            # Initialize disk buffer if specified
                            if entry.get('disk_buffer') == 'DISK':
                                # Sanitize name and subname to prevent path traversal
                                safe_name = entry['name'].replace('..', '').replace('/', '_')
                                safe_subname = entry['subname'].replace('..', '').replace('/', '_')
                                buffer_dir = f"/var/lib/sle/buffer/{safe_name}/{safe_subname}"
                                self.disk_buffers[source_key] = DiskBuffer(buffer_dir)
                                logger.info(f"Disk buffer enabled for {source_key}")
                            
                            # Create and start thread for new watcher
                            thread = threading.Thread(
                                target=watcher.start,
                                args=(self.queue,),
                                daemon=True
                            )
                            thread.start()
                            self.threads.append(thread)
                
                if new_files_found:
                    logger.info(f"Auto-reload complete. Now watching {len(self.watchers)} source(s)")
                else:
                    logger.debug("Auto-reload: no new files found")
                    
            except Exception as e:
                logger.error(f"Error during auto-reload: {e}")
    
    def stop(self):
        """Stop the service"""
        logger.info("Stopping SLE...")
        self.running = False
        
        # Flush all remaining buffers before stopping
        logger.info("Flushing remaining buffers...")
        self._flush_all_buffers()
        
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
