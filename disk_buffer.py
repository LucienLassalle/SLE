"""
Disk buffer / WAL (Write-Ahead Log) for SLE
Provides at-least-once delivery guarantee by persisting logs to disk
"""

import os
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from queue import Queue
import time


logger = logging.getLogger('SLE.DiskBuffer')


class DiskBuffer:
    """Disk-based buffer with Write-Ahead Log for reliable log delivery"""
    
    def __init__(self, buffer_dir: str = "/var/lib/sle/buffer"):
        self.buffer_dir = Path(buffer_dir)
        self.buffer_dir.mkdir(parents=True, exist_ok=True)
        self.pending_dir = self.buffer_dir / "pending"
        self.processing_dir = self.buffer_dir / "processing"
        self.pending_dir.mkdir(exist_ok=True)
        self.processing_dir.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        self.sequence = 0
        self._load_sequence()
        
    def _load_sequence(self):
        """Load the last sequence number from existing files"""
        max_seq = 0
        for file_path in self.pending_dir.glob("*.log"):
            try:
                seq = int(file_path.stem)
                if seq > max_seq:
                    max_seq = seq
            except ValueError:
                pass
        self.sequence = max_seq
        
    def write(self, log_entry: Dict[str, Any]) -> bool:
        """Write a log entry to disk buffer"""
        try:
            with self.lock:
                self.sequence += 1
                file_path = self.pending_dir / f"{self.sequence:010d}.log"
                
                with open(file_path, 'w') as f:
                    json.dump(log_entry, f)
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk
                
                return True
        except Exception as e:
            logger.error(f"Failed to write to disk buffer: {e}")
            return False
    
    def get_pending_files(self) -> List[Path]:
        """Get list of pending log files to replay"""
        files = sorted(self.pending_dir.glob("*.log"))
        return files
    
    def move_to_processing(self, file_path: Path) -> Optional[Path]:
        """Move a file from pending to processing"""
        try:
            new_path = self.processing_dir / file_path.name
            file_path.rename(new_path)
            return new_path
        except Exception as e:
            logger.error(f"Failed to move file to processing: {e}")
            return None
    
    def delete_processed(self, file_path: Path):
        """Delete a successfully processed log file"""
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.error(f"Failed to delete processed file: {e}")
    
    def move_back_to_pending(self, file_path: Path):
        """Move a file back to pending if processing failed"""
        try:
            new_path = self.pending_dir / file_path.name
            if file_path.exists():
                file_path.rename(new_path)
        except Exception as e:
            logger.error(f"Failed to move file back to pending: {e}")
    
    def read_log_entry(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Read a log entry from a file"""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read log file {file_path}: {e}")
            return None
    
    def get_buffer_size(self) -> int:
        """Get the number of pending log entries"""
        return len(list(self.pending_dir.glob("*.log")))
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """Clean up old files (safety mechanism)"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        for directory in [self.pending_dir, self.processing_dir]:
            for file_path in directory.glob("*.log"):
                try:
                    if file_path.stat().st_mtime < cutoff_time:
                        logger.warning(f"Removing old buffer file: {file_path}")
                        file_path.unlink()
                except Exception as e:
                    logger.error(f"Failed to cleanup old file {file_path}: {e}")
