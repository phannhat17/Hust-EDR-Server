export interface Alert {
  id: string;
  rule_name: string;
  match_body: Record<string, any>;
  created_at: string;
  status: 'new' | 'in_progress' | 'resolved' | 'false_positive';
  notes?: string;
  assigned_to?: string;
  description?: string;
  source?: string;
  affected_host?: string;
  severity?: 'low' | 'medium' | 'high';
  raw_data?: any;
  alert_time?: string;
}

export interface Rule {
  filename: string;
  name: string;
  type: string;
  index: string;
  filter: Record<string, any>[];
  alert: string[];
  alert_subject?: string;
  alert_text?: string;
  alert_text_type?: string;
  realert?: Record<string, any>;
  time_window?: Record<string, any>;
  threshold?: number;
  timestamp_field?: string;
  timestamp_format?: string;
  exponential_realert?: Record<string, any>;
  match_enhancements?: Record<string, any>[];
  include?: string[];
  description?: string;
  priority?: number;
  is_enabled?: boolean;
  [key: string]: any;
}

export interface DashboardStats {
  total_alerts: number;
  new_alerts: number;
  resolved_alerts: number;
  false_positives: number;
  active_agents: number;
  total_rules: number;
  active_rules: number;
}

export interface AlertByStatus {
  status: 'new' | 'in_progress' | 'resolved' | 'false_positive';
  count: number;
}

export interface AlertByTime {
  date: string;
  count: number;
}

export interface Agent {
  id: string;
  hostname: string;
  ip_address: string;
  os_info: string;
  version: string;
  status: 'active' | 'inactive';
  last_seen: string;
  registered_at: string;
  // Add any other fields that might be in the API response
} 