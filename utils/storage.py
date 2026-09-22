# utils/storage.py
import os
import shutil
import time
import uuid
import logging
import streamlit as st
from pathlib import Path

# Configure a basic logger for cleanup operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the root directory for all temporary automation files
BASE_TEMP_DIR = Path("./temp_storage")

def _ensure_base_dir():
    """Ensures the root storage directory exists."""
    BASE_TEMP_DIR.mkdir(parents=True, exist_ok=True)

def create_job_workspace() -> Path:
    """
    Creates an isolated, unique temporary folder for a single automation execution.
    Returns a pathlib.Path object pointing to the new directory.
    """
    _ensure_base_dir()
    
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job_dir = BASE_TEMP_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    return job_dir

@st.cache_resource(ttl=600)
def _throttled_cleanup(max_age_seconds: int):
    """
    Internal garbage collector. Caches execution for 10 minutes (600s) globally 
    across all active user sessions to prevent Disk I/O spam on UI reruns.
    """
    _ensure_base_dir()
    now = time.time()
    cleaned_count = 0
    
    for item in BASE_TEMP_DIR.iterdir():
        if item.is_dir():
            try:
                # Check the last modified time of the directory
                folder_age = now - item.stat().st_mtime
                
                if folder_age > max_age_seconds:
                    shutil.rmtree(item, ignore_errors=True)
                    cleaned_count += 1
                    logger.info(f"Purged stale workspace: {item.name} (Age: {int(folder_age/60)} mins)")
            except Exception as e:
                logger.error(f"Failed to clean up workspace {item.name}: {e}")
                
    if cleaned_count > 0:
        logger.info(f"Garbage collection complete: {cleaned_count} workspaces purged.")
        
    # Return a timestamp to satisfy Streamlit's caching requirement
    return time.time()

def cleanup_stale_workspaces(max_age_seconds: int = 3600):
    """
    Scans the base storage directory and aggressively purges any folders 
    older than the specified max_age_seconds (default is 1 hour).
    
    Safe to call at the top of your Streamlit app; execution is automatically throttled.
    """
    _throttled_cleanup(max_age_seconds)