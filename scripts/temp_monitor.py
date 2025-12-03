import time
import os
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

class InvoiceFileHandler(FileSystemEventHandler):
    """Handles file system events for invoice files."""
    
    def __init__(self, on_new_file: Optional[Callable[[str], None]] = None):
        self.on_new_file = on_new_file
        super().__init__()
    
    def on_created(self, event):
        """Called when a file or directory is created."""
        if event.is_directory:
            return
        
        if isinstance(event, FileCreatedEvent):
            file_path = event.src_path
            print(f"Detected new file: {file_path}")
            
            # Trigger callback if provided
            if self.on_new_file:
                try:
                    self.on_new_file(file_path)
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")

class Monitor_Agent:
    """File monitor using watchdog for real-time file detection.

    It detects new files and calls a processing callback.
    """
    def __init__(self, inbox_path: str, on_new_file: Optional[Callable[[str], None]] = None):
        self.inbox_path = inbox_path
        self.on_new_file = on_new_file
        self._observer = None
        self._handler = None

    def start(self):
        """Start monitoring the inbox path."""
        # Create directory if it doesn't exist
        Path(self.inbox_path).mkdir(parents=True, exist_ok=True)
        
        # Setup event handler and observer
        self._handler = InvoiceFileHandler(on_new_file=self.on_new_file)
        self._observer = Observer()
        self._observer.schedule(self._handler, self.inbox_path, recursive=False)
        
        # Start observer
        self._observer.start()
        print(f"Monitoring {self.inbox_path} for new invoices...")

    def stop(self):
        """Stop monitoring."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            print("Monitoring stopped.")