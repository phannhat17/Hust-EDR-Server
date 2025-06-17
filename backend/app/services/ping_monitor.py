"""
Background service to monitor agent ping timeouts.
"""

import threading
import time
import logging
from typing import Dict, Any

from app.storage import FileStorage
from app.config.config import config

logger = logging.getLogger(__name__)

class AgentPingMonitor:
    """Background service to monitor agent ping timeouts."""
    
    def __init__(self):
        self.storage = FileStorage()
        self.running = False
        self.monitor_thread = None
        
        # Ping timeout in seconds (10 minutes)
        self.ping_timeout = config.AGENT_TIMEOUT
        
        # Check interval in seconds (1 minute)
        self.check_interval = 60
        
    def start(self):
        """Start the ping monitor service."""
        if self.running:
            logger.warning("Ping monitor is already running")
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"Agent ping monitor started - checking every {self.check_interval}s, timeout after {self.ping_timeout}s")
        
    def stop(self):
        """Stop the ping monitor service."""
        if not self.running:
            return
            
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Agent ping monitor stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                self._check_agent_timeouts()
            except Exception as e:
                logger.error(f"Error in ping monitor loop: {e}")
                
            # Wait for next check
            time.sleep(self.check_interval)
            
    def _check_agent_timeouts(self):
        """Check all agents for ping timeouts."""
        try:
            current_time = int(time.time())
            timeout_threshold = current_time - self.ping_timeout
            
            # Get all agents
            agents_data = self.storage.get_all_agents()
            if not agents_data:
                return
                
            offline_count = 0
            
            for agent_id, agent in agents_data.items():
                # Only check agents that are currently ONLINE
                if agent.get('status') != 'ONLINE':
                    continue
                    
                last_seen = agent.get('last_seen', 0)
                
                # Check if agent has timed out
                if last_seen < timeout_threshold:
                    logger.info(f"Agent {agent_id} ping timeout - last seen {current_time - last_seen}s ago, marking as OFFLINE")
                    
                    # Update agent status to OFFLINE
                    agent['status'] = 'OFFLINE'
                    agent['last_offline'] = current_time
                    
                    # Save the updated agent
                    self.storage.save_agent(agent_id, agent)
                    offline_count += 1
                    
            if offline_count > 0:
                logger.info(f"Ping monitor: Set {offline_count} agents to OFFLINE due to timeout")
                
        except Exception as e:
            logger.error(f"Error checking agent timeouts: {e}")

# Global ping monitor instance
ping_monitor = AgentPingMonitor() 