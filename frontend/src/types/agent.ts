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
}

export function isAgentOnline(lastSeen: string): boolean {
  const lastSeenDate = new Date(lastSeen);
  const tenMinutesAgo = new Date(Date.now() - 10 * 60 * 1000); // 10 minutes in milliseconds
  return lastSeenDate > tenMinutesAgo;
} 