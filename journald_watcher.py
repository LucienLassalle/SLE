"""
Journald watcher for SLE
Watches systemd journal in real-time using journalctl
"""

import subprocess
import logging
import json as json_module
from queue import Queue


logger = logging.getLogger('SLE.JournaldWatcher')


class JournaldWatcher:
    """Watch systemd journal logs in real-time"""
    
    def __init__(self, labels: dict = None):
        """
        Initialize journald watcher
        
        Args:
            labels: Custom labels to add to all journald logs
        """
        self.labels = labels or {}
        self.running = False
        self.process = None
        
    def start(self, queue: Queue):
        """Start watching journald"""
        self.running = True
        
        # journalctl -f -o json --no-pager
        # -f: follow (tail mode)
        # -o json: output as JSON
        # --no-pager: disable pager
        cmd = ['journalctl', '-f', '-o', 'json', '--no-pager']
        
        logger.info("Started watching journald (systemd journal)")
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            for line in iter(self.process.stdout.readline, ''):
                if not self.running:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # Parse JSON entry from journalctl
                    entry = json_module.loads(line)
                    
                    # Extract message
                    message = entry.get('MESSAGE', '')
                    if not message:
                        continue
                    
                    # Extract systemd unit or syslog identifier
                    unit = entry.get('_SYSTEMD_UNIT', '')
                    identifier = entry.get('SYSLOG_IDENTIFIER', 'unknown')
                    
                    # Determine service name (use unit if available, otherwise identifier)
                    service_name = unit.replace('.service', '') if unit else identifier
                    
                    # Create log entry for queue
                    log_entry = {
                        'line': message,
                        'name': 'journald',
                        'subname': service_name.upper(),
                        'filepath': f'journald:{service_name}'
                    }
                    
                    # Add custom labels if present
                    if self.labels:
                        log_entry['labels'] = self.labels.copy()
                    
                    queue.put(log_entry)
                    
                except json_module.JSONDecodeError:
                    logger.debug(f"Failed to parse journalctl JSON: {line[:100]}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing journald entry: {e}")
                    continue
        
        except FileNotFoundError:
            logger.error("journalctl command not found. Is systemd installed?")
        except Exception as e:
            logger.error(f"Error watching journald: {e}")
        finally:
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
    
    def stop(self):
        """Stop watching journald"""
        logger.info("Stopping journald watcher")
        self.running = False
        if self.process:
            self.process.terminate()
