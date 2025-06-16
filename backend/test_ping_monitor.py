#!/usr/bin/env python3
"""
Test script to verify the new ping-based agent monitoring system.
"""

import time
import json
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.ping_monitor import ping_monitor
from app.storage import FileStorage
from app.config.config import config

def test_ping_monitor():
    """Test the ping monitor functionality."""
    print("Testing Ping Monitor System")
    print("=" * 50)
    
    # Initialize storage
    storage = FileStorage('test_data')
    
    # Create test agent data
    current_time = int(time.time())
    
    # Agent 1: Online but will timeout (last seen 15 minutes ago)
    old_time = current_time - 900  # 15 minutes ago
    agent1 = {
        'agent_id': 'test-agent-1',
        'hostname': 'test-host-1',
        'ip_address': '192.168.1.100',
        'status': 'ONLINE',
        'last_seen': old_time,
        'registration_time': old_time
    }
    
    # Agent 2: Online and recent (last seen 2 minutes ago)
    recent_time = current_time - 120  # 2 minutes ago
    agent2 = {
        'agent_id': 'test-agent-2',
        'hostname': 'test-host-2',
        'ip_address': '192.168.1.101',
        'status': 'ONLINE',
        'last_seen': recent_time,
        'registration_time': recent_time
    }
    
    # Agent 3: Already offline
    agent3 = {
        'agent_id': 'test-agent-3',
        'hostname': 'test-host-3',
        'ip_address': '192.168.1.102',
        'status': 'OFFLINE',
        'last_seen': old_time,
        'registration_time': old_time
    }
    
    # Save test agents
    storage.save_agent('test-agent-1', agent1)
    storage.save_agent('test-agent-2', agent2)
    storage.save_agent('test-agent-3', agent3)
    storage.force_save()
    
    print(f"Created test agents:")
    print(f"  Agent 1: ONLINE, last seen {(current_time - old_time)//60} minutes ago (should timeout)")
    print(f"  Agent 2: ONLINE, last seen {(current_time - recent_time)//60} minutes ago (should stay online)")
    print(f"  Agent 3: OFFLINE (should stay offline)")
    print()
    
    # Test ping monitor
    print("Testing ping monitor...")
    
    # Create a ping monitor instance with test storage
    class TestPingMonitor:
        def __init__(self):
            self.storage = storage
            self.ping_timeout = config.AGENT_TIMEOUT
    
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
                        print(f"Agent {agent_id} ping timeout - last seen {current_time - last_seen}s ago, marking as OFFLINE")
                        
                        # Update agent status to OFFLINE
                        agent['status'] = 'OFFLINE'
                        agent['last_offline'] = current_time
                        
                        # Save the updated agent
                        self.storage.save_agent(agent_id, agent)
                        offline_count += 1
                        
                if offline_count > 0:
                    print(f"Ping monitor: Set {offline_count} agents to OFFLINE due to timeout")
                else:
                    print("Ping monitor: No agents timed out")
                    
            except Exception as e:
                print(f"Error checking agent timeouts: {e}")
    
    test_monitor = TestPingMonitor()
    test_monitor._check_agent_timeouts()
    
    # Check results
    print("\nResults after ping monitor check:")
    all_agents = storage.get_all_agents()
    for agent_id, agent in all_agents.items():
        status = agent.get('status')
        last_seen = agent.get('last_seen', 0)
        minutes_ago = (current_time - last_seen) // 60
        print(f"  {agent_id}: {status} (last seen {minutes_ago} minutes ago)")
    
    # Cleanup
    import shutil
    if os.path.exists('test_data'):
        shutil.rmtree('test_data')
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_ping_monitor()