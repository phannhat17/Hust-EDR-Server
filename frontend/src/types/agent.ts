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
  mac_address?: string;
  
  /**
   * Username running the agent
   */
  username?: string;
  
  /**
   * OS information (simplified)
   */
  os_info: string;
  
  /**
   * Full OS version string
   */
  os_version_full?: string;
  
  /**
   * Agent version
   */
  version?: string;
  
  /**
   * Agent status (online, offline, etc.)
   */
  status: string;
  
  /**
   * Current CPU usage percentage
   */
  cpu_usage?: number;
  
  /**
   * Current memory usage percentage
   */
  memory_usage?: number;
  
  /**
   * System uptime in seconds
   */
  uptime?: number;
  
  /**
   * Timestamp of last status update (milliseconds)
   */
  last_seen: number;
  
  /**
   * Timestamp of agent registration (milliseconds)
   */
  registered_at: number;
} 