"""
ElastAlert enhancement module for automatically adding auto-response fields to alerts.
This module can be used with the ElastAlert 'match_enhancements' option to automatically
add auto-response fields to alerts based on the alert data.

Usage in rule file:
```yaml
match_enhancements:
  - "elastalert_modules.enhance_auto_response:add_auto_response_fields"
```
"""

import logging

logger = logging.getLogger('elastalert')

def add_auto_response_fields(match, rule):
    """
    Add auto-response fields to an alert based on its content.
    
    Args:
        match: The alert data
        rule: The rule that triggered the alert
        
    Returns:
        dict: Enhanced alert data with auto-response fields
    """
    # Skip if auto-response is already defined or explicitly disabled
    if match.get('auto_response_type') or match.get('auto_response_disabled'):
        return match
    
    # Get rule name for logging
    rule_name = rule.get('name', 'unknown')
    logger.info(f"Enhancing alert from rule '{rule_name}' with auto-response fields")
    
    try:
        # Determine auto-response type based on alert content
        # This is where you would implement your logic to decide what auto-response action to take
        
        # Example: Delete malicious files
        if 'file' in match and match.get('tags', []) and 'malware' in match.get('tags', []):
            file_path = match.get('file', {}).get('path')
            if file_path:
                match['auto_response_type'] = 'DELETE_FILE'
                match['auto_response_file_path'] = file_path
                logger.info(f"Added DELETE_FILE auto-response for file: {file_path}")
                return match
                
        # Example: Kill malicious processes
        if 'process' in match and match.get('process', {}).get('pid') and 'malicious' in match.get('tags', []):
            pid = match.get('process', {}).get('pid')
            if pid:
                match['auto_response_type'] = 'KILL_PROCESS'
                match['auto_response_pid'] = str(pid)
                logger.info(f"Added KILL_PROCESS auto-response for PID: {pid}")
                return match
                
        # Example: Block suspicious IPs
        if 'destination' in match and match.get('destination', {}).get('ip') and 'c2_traffic' in match.get('tags', []):
            ip = match.get('destination', {}).get('ip')
            if ip:
                match['auto_response_type'] = 'BLOCK_IP'
                match['auto_response_ip'] = ip
                logger.info(f"Added BLOCK_IP auto-response for IP: {ip}")
                return match
        
        logger.debug(f"No auto-response fields added for alert from rule '{rule_name}'")
        return match
    except Exception as e:
        logger.error(f"Error enhancing alert with auto-response fields: {e}")
        return match
        
def add_network_isolation_response(match, rule):
    """
    Specialized enhancement to add network isolation auto-response.
    
    Args:
        match: The alert data
        rule: The rule that triggered the alert
        
    Returns:
        dict: Enhanced alert data with network isolation fields
    """
    # Skip if auto-response is already defined or explicitly disabled
    if match.get('auto_response_type') or match.get('auto_response_disabled'):
        return match
    
    # Only apply to alerts with specific tags or conditions
    if 'ransomware' in match.get('tags', []) or match.get('severity', 0) >= 90:
        hostname = match.get('host', {}).get('hostname')
        if hostname:
            match['auto_response_type'] = 'NETWORK_ISOLATE'
            match['auto_response_allowed_ips'] = '8.8.8.8,8.8.4.4' # Allow DNS
            logger.info(f"Added NETWORK_ISOLATE auto-response for host: {hostname}")
    
    return match 