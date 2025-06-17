"""
Storage implementation for the EDR backend using JSON files.
"""

import os
import json
import time
import threading
from app.logging_setup import get_logger

# Set up logging
logger = get_logger('app.storage')
debug_logger = get_logger('app.storage.debug')

class FileStorage:
    """Storage for agent data using JSON files."""
    
    def __init__(self, storage_dir='data'):
        self.storage_dir = storage_dir
        self.agents_file = os.path.join(storage_dir, 'agents.json')
        self.results_file = os.path.join(storage_dir, 'command_results.json')
        self.ioc_matches_file = os.path.join(storage_dir, 'ioc_matches.json')
        
        # Create storage directory
        os.makedirs(storage_dir, exist_ok=True)
        
        # In-memory data structures
        self.agents = {}
        self.ioc_matches = {}
        
        # For optimized saving
        self.dirty_agents = False
        self.last_save_time = 0
        self.save_interval = 60  # Save at most once per minute
        self.agent_mutex = threading.RLock()
        
        # Load existing data
        self._load_data()
        logger.info(f"FileStorage initialized at {storage_dir}")
    
    def _load_data(self):
        """Load all data from storage files."""
        self._load_agents()
        self._load_ioc_matches()
        
        # Ensure command results file exists
        if not os.path.exists(self.results_file):
            self._save_json({}, self.results_file)
    
    def _load_agents(self):
        """Load agents from file."""
        self.agents = self._load_json(self.agents_file, "agents")
    
    def _load_ioc_matches(self):
        """Load IOC matches from file."""
        self.ioc_matches = self._load_json(self.ioc_matches_file, "IOC matches")
        if self.ioc_matches is None or not isinstance(self.ioc_matches, dict):
            # Ensure ioc_matches is a dictionary
            logger.warning(f"IOC matches data is not a dictionary, resetting to empty dictionary")
            self.ioc_matches = {}
            self._save_json(self.ioc_matches, self.ioc_matches_file)
    
    def _load_json(self, file_path, data_type="data"):
        """Generic JSON file loader with error handling."""
        if not os.path.exists(file_path):
            logger.info(f"No existing {data_type} found")
            return {}
            
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse {data_type} file, using empty database")
            return {}
        except Exception as e:
            logger.error(f"Error loading {data_type}: {e}")
            return {}
    
    def _save_json(self, data, file_path):
        """Generic JSON file saver with error handling."""
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving to {file_path}: {e}")
            return False
    
    def _save_agents(self, force=False):
        """Save agents to file with batching.
        
        Args:
            force (bool): Force save regardless of time elapsed
        """
        with self.agent_mutex:
            current_time = time.time()
            elapsed = current_time - self.last_save_time
            
            # Only save if dirty and either forced or enough time has passed
            if self.dirty_agents and (force or elapsed >= self.save_interval):
                print(f"[DEBUG] Actually saving to file (elapsed: {elapsed}s)")
                success = self._save_json(self.agents, self.agents_file)
                if success:
                    self.dirty_agents = False
                    self.last_save_time = current_time
                    debug_logger.debug(f"Saved {len(self.agents)} agents to storage (elapsed: {int(elapsed)}s)")
                return success
            else:
                print(f"[DEBUG] Skipping save - elapsed: {elapsed}s, dirty: {self.dirty_agents}, force: {force}")
            return True  # No save needed
    
    def save_ioc_match(self, match_id, match_data):
        """Save IOC match data."""
        try:
            # Ensure ioc_matches is a dictionary
            if not isinstance(self.ioc_matches, dict):
                logger.error(f"ioc_matches is not a dictionary: {type(self.ioc_matches)}")
                self.ioc_matches = {}
            
            self.ioc_matches[match_id] = match_data
            success = self._save_json(self.ioc_matches, self.ioc_matches_file)
            if success:
                debug_logger.info(f"Saved IOC match {match_id} to storage")
            return success
        except Exception as e:
            logger.error(f"Error saving IOC match: {e}")
            # Try to recover by resetting to empty dict
            self.ioc_matches = {match_id: match_data}
            return self._save_json(self.ioc_matches, self.ioc_matches_file)
    
    def get_agent(self, agent_id):
        """Get an agent by ID."""
        with self.agent_mutex:
            return self.agents.get(agent_id)
    
    def get_all_agents(self):
        """Get all agents."""
        with self.agent_mutex:
            return self.agents.copy()
    
    def save_agent(self, agent_id, agent_data):
        """Save agent data with optimized writes."""
        with self.agent_mutex:
            self.agents[agent_id] = agent_data
            self.dirty_agents = True
            print(f"[DEBUG] save_agent called for {agent_id}, status: {agent_data.get('status')}")
            
            # Perform actual save based on time throttling
            result = self._save_agents(force=False)
            print(f"[DEBUG] _save_agents returned: {result}")
            return result
    
    def force_save(self):
        """Force save any pending changes."""
        return self._save_agents(force=True) 