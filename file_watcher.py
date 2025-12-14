"""
Log file watcher for SLE
Watches log files in real-time (like tail -f)
"""

import os
import time
import logging
from typing import Dict, Any
from queue import Queue


logger = logging.getLogger('SLE.FileWatcher')


class LogFileWatcher:
    """Watch a log file in real-time (like tail -f)"""
    
    def __init__(self, filepath: str, name: str, subname: str, delimiter: str = "\n", 
                 labels: Dict[str, str] = None, rate_limit: float = None, buffer_size: int = None):
        self.filepath = filepath
        self.name = name
        self.subname = subname
        self.delimiter = delimiter
        self.labels = labels or {}
        self.rate_limit = rate_limit
        self.buffer_size = buffer_size
        self.file = None
        self.running = False
        
    def start(self, queue: Queue):
        """Start watching the file"""
        self.running = True
        try:
            # Open file and seek to end
            self.file = open(self.filepath, 'r')
            self.file.seek(0, os.SEEK_END)
            
            logger.info(f"Started watching {self.filepath} [{self.name}/{self.subname}]")
            
            while self.running:
                line = self.file.readline()
                if line:
                    # Send line to queue with labels
                    log_entry = {
                        'line': line.rstrip(self.delimiter),
                        'name': self.name,
                        'subname': self.subname,
                        'filepath': self.filepath
                    }
                    if self.labels:
                        log_entry['labels'] = self.labels
                    queue.put(log_entry)
                else:
                    # No new line, wait a bit
                    time.sleep(0.1)
                    
        except FileNotFoundError:
            logger.error(f"File not found: {self.filepath}")
        except Exception as e:
            logger.error(f"Error watching {self.filepath}: {e}")
        finally:
            if self.file:
                self.file.close()
    
    def stop(self):
        """Stop watching the file"""
        self.running = False
