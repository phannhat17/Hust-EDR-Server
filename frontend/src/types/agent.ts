/**
 * Agent type definitions
 */

/**
 * Represents an EDR agent
 */
export interface Agent {
  /**
   * Unique agent ID
   */
  id: string;
  
  /**
   * Agent hostname
   */
  hostname: string;
  
  /**
   * Agent IP address
   */
  ip_address: string;
  
  /**
   * Agent MAC address
   */
  mac_address: string;
  
  /**
   * OS information (simplified)
   */
  os: string;
  
  /**
   * OS information formatted for display
   */
  os_info?: string;
  
  /**
   * Full OS version string
   */
  os_version_full?: string;
  
  /**
   * Username running the agent
   */
  username: string;
  
  /**
   * Current CPU usage percentage
   */
  cpu_usage: number;
  
  /**
   * Current memory usage percentage
   */
  memory_usage: number;
  
  /**
   * System uptime in seconds
   */
  uptime: number;
  
  /**
   * Agent version
   */
  version: string;
  
  /**
   * Timestamp of agent registration (milliseconds)
   */
  registered_at: string;
  
  /**
   * Timestamp of last status update (milliseconds)
   */
  last_seen: string;
  
  /**
   * Last IOC match information
   */
  last_ioc_match?: {
    timestamp: number;
    type: string;
    ioc_value: string;
    severity: string;
  };
  
  /**
   * IOC matches history
   */
  ioc_matches?: IOCMatch[];
}

/**
 * Represents a severity level
 */
export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';

/**
 * Represents an IOC match
 */
export interface IOCMatch {
  /**
   * Unique report ID
   */
  report_id: string;
  
  /**
   * Agent ID that reported the match
   */
  agent_id: string;
  
  /**
   * Timestamp when the match occurred
   */
  timestamp: number;
  
  /**
   * Type of IOC (IOC_IP, IOC_HASH, IOC_URL)
   */
  type: string;
  
  /**
   * The IOC value that was matched
   */
  ioc_value: string;
  
  /**
   * The actual value that matched
   */
  matched_value: string;
  
  /**
   * Additional context about the match
   */
  context: string;
  
  /**
   * Severity level
   */
  severity: SeverityLevel;
  
  /**
   * Action taken in response to the match
   */
  action_taken: string | null;
  
  /**
   * Whether the action was successful
   */
  action_success: boolean;
  
  /**
   * Message from the action
   */
  action_message: string;
  
  /**
   * When the server received the report
   */
  server_received: number;
}

/**
 * Check if an agent is online (last seen within 5 minutes)
 */
export function isAgentOnline(lastSeen: string | number): boolean {
  if (!lastSeen) return false;
  
  const lastSeenTime = typeof lastSeen === 'string' ? parseInt(lastSeen, 10) : lastSeen;
  const now = Date.now();
  // Consider online if seen in the last 5 minutes
  return now - lastSeenTime < 5 * 60 * 1000;
} 