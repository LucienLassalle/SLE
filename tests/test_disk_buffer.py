#!/usr/bin/env python3
"""
Tests for disk buffer and auto-reload features
"""

import os
import sys
import time
import json
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disk_buffer import DiskBuffer


def test_disk_buffer():
    """Test disk buffer write/read/replay"""
    print("Testing disk buffer...")
    
    # Create temporary buffer directory
    with tempfile.TemporaryDirectory() as tmpdir:
        buffer = DiskBuffer(tmpdir)
        
        # Test write
        log_entry = {
            'line': 'Test log message',
            'name': 'test',
            'subname': 'TEST',
            'filepath': '/tmp/test.log'
        }
        
        result = buffer.write(log_entry)
        assert result, "Failed to write to disk buffer"
        print("✓ Write to disk buffer successful")
        
        # Test get pending files
        pending = buffer.get_pending_files()
        assert len(pending) == 1, f"Expected 1 pending file, got {len(pending)}"
        print(f"✓ Found {len(pending)} pending file(s)")
        
        # Test read
        read_entry = buffer.read_log_entry(pending[0])
        assert read_entry is not None, "Failed to read log entry"
        assert read_entry['line'] == log_entry['line'], "Log entry mismatch"
        print("✓ Read from disk buffer successful")
        
        # Test move to processing
        processing_path = buffer.move_to_processing(pending[0])
        assert processing_path is not None, "Failed to move to processing"
        print("✓ Move to processing successful")
        
        # Test delete processed
        buffer.delete_processed(processing_path)
        assert not processing_path.exists(), "File still exists after delete"
        print("✓ Delete processed successful")
        
        # Test buffer size
        size = buffer.get_buffer_size()
        assert size == 0, f"Expected buffer size 0, got {size}"
        print("✓ Buffer size is 0 after cleanup")
    
    print("✅ All disk buffer tests passed!\n")


def test_glob_pattern_resolution():
    """Test glob pattern resolution in config"""
    print("Testing glob pattern resolution...")
    
    # Create temporary files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create test files
        (tmppath / "app1.log").touch()
        (tmppath / "app2.log").touch()
        (tmppath / "app3.log").touch()
        (tmppath / "other.txt").touch()
        
        # Test glob pattern
        import glob as glob_module
        pattern = str(tmppath / "*.log")
        matched = glob_module.glob(pattern)
        
        assert len(matched) == 3, f"Expected 3 matches, got {len(matched)}"
        print(f"✓ Glob pattern '{pattern}' matched {len(matched)} files")
        
        # Test recursive glob
        subdir = tmppath / "subdir"
        subdir.mkdir()
        (subdir / "sub1.log").touch()
        (subdir / "sub2.log").touch()
        
        pattern = str(tmppath / "**/*.log")
        matched = glob_module.glob(pattern, recursive=True)
        
        assert len(matched) == 5, f"Expected 5 matches, got {len(matched)}"
        print(f"✓ Recursive glob pattern '{pattern}' matched {len(matched)} files")
    
    print("✅ All glob pattern tests passed!\n")


def test_multiple_writes():
    """Test multiple writes and replay"""
    print("Testing multiple writes and replay...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        buffer = DiskBuffer(tmpdir)
        
        # Write multiple entries
        for i in range(10):
            log_entry = {
                'line': f'Test log message {i}',
                'name': 'test',
                'subname': 'TEST',
                'filepath': '/tmp/test.log'
            }
            buffer.write(log_entry)
        
        # Check pending count
        pending = buffer.get_pending_files()
        assert len(pending) == 10, f"Expected 10 pending files, got {len(pending)}"
        print(f"✓ Written 10 log entries to disk")
        
        # Simulate replay
        processed_count = 0
        for file_path in pending:
            entry = buffer.read_log_entry(file_path)
            if entry:
                processing_path = buffer.move_to_processing(file_path)
                if processing_path:
                    # Simulate successful send
                    buffer.delete_processed(processing_path)
                    processed_count += 1
        
        assert processed_count == 10, f"Expected to process 10 entries, processed {processed_count}"
        print(f"✓ Replayed and deleted 10 entries")
        
        # Verify cleanup
        size = buffer.get_buffer_size()
        assert size == 0, f"Expected buffer size 0 after replay, got {size}"
        print("✓ Buffer empty after replay")
    
    print("✅ All replay tests passed!\n")


if __name__ == '__main__':
    print("=" * 60)
    print("SLE Disk Buffer and Auto-Reload Tests")
    print("=" * 60 + "\n")
    
    try:
        test_disk_buffer()
        test_glob_pattern_resolution()
        test_multiple_writes()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
