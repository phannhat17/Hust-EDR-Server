"""
ElastAlert client for accessing alerts and rules from Elasticsearch.
"""

import os
import json
import yaml
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from elasticsearch import Elasticsearch
from app.config.config import config

logger = logging.getLogger('app.elastalert')

class ElastAlertClient:
    def __init__(self, grpc_server=None):
        """Initialize the ElastAlert client using the application config.
        
        Args:
            grpc_server: Optional gRPC server instance for sending commands
        """
        # Setup Elasticsearch client
        try:
            self.es_client = Elasticsearch(**config.get_elasticsearch_config())
            logger.info(f"Connected to Elasticsearch at {config.ELASTICSEARCH_HOST}:{config.ELASTICSEARCH_PORT}")
            
            # Check if the ElastAlert index exists or find available indices
            try:
                indices = list(self.es_client.indices.get("*elastalert*").keys())
                if indices:
                    logger.info(f"Found ElastAlert indices: {', '.join(indices)}")
                    # Use the first index if we found any
                    self.alerts_index = indices[0] 
                    logger.info(f"Using '{self.alerts_index}' as primary ElastAlert index")
                else:
                    # Fall back to config
                    self.alerts_index = config.ELASTALERT_INDEX
                    logger.warning(f"No ElastAlert indices found, falling back to configured index: {self.alerts_index}")
            except Exception as e:
                # Fall back to config
                self.alerts_index = config.ELASTALERT_INDEX
                logger.warning(f"Error detecting ElastAlert indices: {e}, using configured index: {self.alerts_index}")
                
        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            self.es_client = None
            self.alerts_index = config.ELASTALERT_INDEX
        
        # ElastAlert settings
        self.rules_dir = config.ELASTALERT_RULES_DIR
        
        # Keep a reference to the gRPC server
        self.grpc_server = grpc_server
        
        # Ensure rules directory exists
        Path(self.rules_dir).mkdir(parents=True, exist_ok=True)
    
    def get_alerts(self, limit=100):
        """Get alerts from ElastAlert's Elasticsearch index.
        
        Args:
            limit (int): Maximum number of alerts to return
            
        Returns:
            list: List of alerts
        """
        # Return empty list if Elasticsearch is not connected
        if not self.es_client:
            logger.warning("Elasticsearch client not connected")
            return []
            
        # Simplify the query to get all documents
        query = {
            "query": {
                "match_all": {}
            },
            "sort": [
                {"@timestamp": {"order": "desc"}}
            ],
            "size": limit
        }
        
        try:
            # Log the index we're searching
            logger.info(f"Searching exact index name: {self.alerts_index}")
            
            # Check if index exists
            if not self.es_client.indices.exists(index=self.alerts_index):
                logger.error(f"Index {self.alerts_index} does not exist")
                return []
                
            # Use the exact index name without pattern matching
            response = self.es_client.search(
                index=self.alerts_index,
                body=query
            )
            
            # Log hit count
            logger.info(f"Found {len(response['hits']['hits'])} alerts in index {self.alerts_index}")
            
            alerts = []
            for hit in response['hits']['hits']:
                match_body = hit['_source'].get('match_body', {})
                alert = {
                    'id': hit['_id'],
                    'timestamp': hit['_source'].get('@timestamp', ''),
                    'rule_name': hit['_source'].get('rule_name', 'Unknown Rule'),
                    'raw_data': hit['_source'],
                    'status': hit['_source'].get('edr_status', 'new'),
                    'analysis_notes': hit['_source'].get('edr_notes', ''),
                    'analyzed_by': hit['_source'].get('edr_assigned_to', ''),
                    'edr_id': match_body.get('edr_id', ''),
                    'host_hostname': match_body.get('host', {}).get('hostname', ''),
                    'user_name': match_body.get('user', {}).get('name', ''),
                    'process_command_line': match_body.get('process', {}).get('command_line', ''),
                    'process_pid': match_body.get('process', {}).get('pid', ''),
                    'process_parent_pid': match_body.get('process', {}).get('parent', {}).get('pid', ''),
                    'event_created': match_body.get('event', {}).get('created', ''),
                }
                
                alerts.append(alert)
                
            return alerts
            
        except Exception as e:
            logger.error(f"Error fetching alerts: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def update_alert_status(self, alert_id, status, notes=None, assigned_to=None):
        """Update the status of an alert in Elasticsearch.
        
        Args:
            alert_id (str): ID of the alert to update
            status (str): New status (new, in_review, in_progress, resolved, false_positive, processed)
            notes (str, optional): Analysis notes
            assigned_to (str, optional): Analyst assigned to the alert
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Return false if Elasticsearch is not connected
        if not self.es_client:
            logger.warning("Elasticsearch client not connected")
            return False
            
        doc = {
            "edr_status": status,
            "edr_updated_at": datetime.now().isoformat()
        }
        
        if notes is not None:
            doc["edr_notes"] = notes
            
        if assigned_to is not None:
            doc["edr_assigned_to"] = assigned_to
            
        # Add status-specific timestamps
        if status == "resolved":
            doc["edr_resolved_at"] = datetime.now().isoformat()
        elif status == "in_progress":
            doc["edr_in_progress_at"] = datetime.now().isoformat()
        elif status == "processed":
            doc["edr_processed_at"] = datetime.now().isoformat()
            
        try:
            logger.info(f"Updating alert {alert_id} with status '{status}' in index {self.alerts_index}")
            
            # Try to update the document
            result = self.es_client.update(
                index=self.alerts_index,
                id=alert_id,
                body={"doc": doc},
                retry_on_conflict=3
            )
            
            logger.info(f"Alert update result: {result.get('result', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Error updating alert status: {e}")
            
            # Try to update in the broader index pattern if the first attempt failed
            try:
                broader_indices = list(self.es_client.indices.get("*elastalert*").keys())
                for index in broader_indices:
                    if index == self.alerts_index:
                        continue
                        
                    try:
                        logger.info(f"Trying to update alert in alternative index: {index}")
                        result = self.es_client.update(
                            index=index,
                            id=alert_id,
                            body={"doc": doc},
                            retry_on_conflict=3
                        )
                        logger.info(f"Alert update succeeded in index {index}")
                        return True
                    except Exception as inner_e:
                        logger.debug(f"Failed to update in index {index}: {inner_e}")
                        continue
            except Exception as outer_e:
                logger.error(f"Error searching for alternative indices: {outer_e}")
                
            return False
    
    def get_rules(self):
        """Get all ElastAlert rules.
        
        Returns:
            list: List of rule objects
        """
        rules = []
        
        logger.info(f"Looking for rule files in directory: {self.rules_dir}")
        
        try:
            rule_files = list(Path(self.rules_dir).glob('*.yaml'))
            logger.info(f"Found {len(rule_files)} rule files: {[f.name for f in rule_files]}")
            
            for file_path in rule_files:
                try:
                    rule = self._read_rule_file(file_path)
                    rule['filename'] = file_path.name
                    rules.append(rule)
                    logger.info(f"Successfully read rule file: {file_path.name}")
                except Exception as e:
                    logger.error(f"Error reading rule file {file_path}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error listing rule files: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
        logger.info(f"Returning {len(rules)} rules")
        return rules
    
    def get_rule(self, filename):
        """Get a specific ElastAlert rule.
        
        Args:
            filename (str): Name of the rule file
            
        Returns:
            dict: Rule object or None if not found
        """
        file_path = Path(self.rules_dir) / filename
        
        logger.info(f"Looking for rule file: {file_path}")
        
        if not file_path.exists():
            logger.error(f"Rule file does not exist: {file_path}")
            return None
            
        try:
            rule = self._read_rule_file(file_path)
            rule['filename'] = filename
            logger.info(f"Successfully read rule file: {filename}")
            return rule
        except Exception as e:
            logger.error(f"Error reading rule file {file_path}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def save_rule(self, rule_data):
        """Save an ElastAlert rule.
        
        Args:
            rule_data (dict): Rule data
            
        Returns:
            tuple: (success, filename)
        """
        # Validate required fields
        required_fields = ['name', 'type', 'index', 'alert']
        for field in required_fields:
            if field not in rule_data:
                return False, f"Missing required field: {field}"
        
        # Generate filename from rule name if not provided
        filename = rule_data.get('filename')
        if not filename:
            filename = self._generate_filename(rule_data['name'])
            
        # Handle special fields
        if 'extra_settings' in rule_data:
            # Merge extra_settings into the rule data
            extra_settings = rule_data.pop('extra_settings')
            if isinstance(extra_settings, dict):
                rule_data.update(extra_settings)
                
        # Remove metadata fields
        if 'filename' in rule_data:
            del rule_data['filename']
            
        file_path = Path(self.rules_dir) / filename
        
        try:
            with open(file_path, 'w') as f:
                yaml.dump(rule_data, f, default_flow_style=False)
                
            # Restart ElastAlert if running in Docker
            if config.ELASTALERT_DOCKER:
                self._restart_elastalert()
                
            return True, filename
        except Exception as e:
            logger.error(f"Error saving rule file {file_path}: {e}")
            return False, str(e)
    
    def delete_rule(self, filename):
        """Delete an ElastAlert rule.
        
        Args:
            filename (str): Name of the rule file
            
        Returns:
            bool: True if successful, False otherwise
        """
        file_path = Path(self.rules_dir) / filename
        
        if not file_path.exists():
            return False
            
        try:
            file_path.unlink()
            
            # Restart ElastAlert if running in Docker
            if config.ELASTALERT_DOCKER:
                self._restart_elastalert()
                
            return True
        except Exception as e:
            logger.error(f"Error deleting rule file {file_path}: {e}")
            return False
    
    def _read_rule_file(self, file_path):
        """Read an ElastAlert rule file.
        
        Args:
            file_path (pathlib.Path): Path to the rule file
            
        Returns:
            dict: Rule object
        """
        logger.info(f"Reading rule file: {file_path}")
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
            logger.debug(f"Rule file content: {content[:100]}...")
            rule = yaml.safe_load(content)
            
            if not isinstance(rule, dict):
                logger.error(f"Rule file does not contain a valid YAML dictionary: {file_path}")
                raise ValueError(f"Invalid rule format in {file_path}")
                
            return rule
        except yaml.YAMLError as e:
            logger.error(f"YAML syntax error in rule file {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error reading rule file {file_path}: {e}")
            raise
    
    def _generate_filename(self, rule_name):
        """Generate a filename from a rule name.
        
        Args:
            rule_name (str): Name of the rule
            
        Returns:
            str: Generated filename
        """
        # Convert to lowercase, replace spaces with underscores, and add .yaml extension
        filename = rule_name.lower().replace(' ', '_')
        
        # Remove special characters
        filename = ''.join(c for c in filename if c.isalnum() or c == '_')
        
        # Add timestamp to ensure uniqueness
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{filename}_{timestamp}.yaml"
    
    def _restart_elastalert(self):
        """Restart the ElastAlert Docker container."""
        try:
            container_name = config.ELASTALERT_CONTAINER
            subprocess.run(['docker', 'restart', container_name], check=True)
            logger.info(f"Restarted ElastAlert container: {container_name}")
            return True
        except Exception as e:
            logger.error(f"Error restarting ElastAlert container: {e}")
            return False

    def _stop_elastalert(self):
        """Stop the ElastAlert Docker container."""
        try:
            container_name = config.ELASTALERT_CONTAINER
            subprocess.run(['docker', 'stop', container_name], check=True)
            logger.info(f"Stopped ElastAlert container: {container_name}")
            return True
        except Exception as e:
            logger.error(f"Error stopping ElastAlert container: {e}")
            return False

    def _start_elastalert(self):
        """Start the ElastAlert Docker container."""
        try:
            container_name = config.ELASTALERT_CONTAINER
            subprocess.run(['docker', 'start', container_name], check=True)
            logger.info(f"Started ElastAlert container: {container_name}")
            return True
        except Exception as e:
            logger.error(f"Error starting ElastAlert container: {e}")
            return False

    def _get_elastalert_status(self):
        """Get the status of the ElastAlert Docker container."""
        try:
            container_name = config.ELASTALERT_CONTAINER
            result = subprocess.run(
                ['docker', 'inspect', '--format={{.State.Status}}', container_name], 
                capture_output=True, 
                text=True, 
                check=True
            )
            status = result.stdout.strip()
            logger.info(f"ElastAlert container status: {status}")
            return status
        except subprocess.CalledProcessError:
            logger.warning(f"ElastAlert container {config.ELASTALERT_CONTAINER} not found or not accessible")
            return "not_found"
        except Exception as e:
            logger.error(f"Error getting ElastAlert container status: {e}")
            return "error" 