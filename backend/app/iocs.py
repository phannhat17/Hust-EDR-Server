"""
IOC management module for EDR.
Provides functionality to store, manage, and distribute IOCs to agents.
"""

import os
import json
import logging
import hashlib
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.config.config import config

# Configure logging
logger = logging.getLogger('app.iocs')

class IOCManager:
    """Manager for Indicators of Compromise (IOCs)."""
    
    def __init__(self, storage_dir='data/iocs'):
        """Initialize the IOC manager.
        
        Args:
            storage_dir (str): Directory to store IOC data
        """
        self.storage_dir = storage_dir
        self.iocs_file = os.path.join(storage_dir, 'iocs.json')
        self.version_file = os.path.join(storage_dir, 'version.json')
        
        # Create storage directory if it doesn't exist
        os.makedirs(storage_dir, exist_ok=True)
        
        # Initialize IOC data structure
        self.iocs = {
            'ip_addresses': {},    # IP -> {added_at, description, severity}
            'file_hashes': {},     # Hash -> {hash_type, added_at, description, severity}
            'urls': {},            # URL -> {added_at, description, severity}
            'process_names': {}    # Name -> {added_at, description, severity}
        }
        
        # Initialize version tracking
        self.version = {
            'version': 1,
            'updated_at': int(time.time()),
            'hash': ''
        }
        
        # Load existing IOCs if available
        self._load_iocs()
        self._load_version()
    
    def _load_iocs(self):
        """Load IOCs from file."""
        if os.path.exists(self.iocs_file):
            with open(self.iocs_file, 'r') as f:
                try:
                    self.iocs = json.load(f)
                    logger.info(f"Loaded IOCs: {self._count_iocs()} total indicators")
                except json.JSONDecodeError:
                    logger.error("Failed to parse IOCs file, using empty database")
        else:
            logger.info("No existing IOCs found, starting with empty database")
            self._save_iocs()
    
    def _load_version(self):
        """Load version information from file."""
        if os.path.exists(self.version_file):
            with open(self.version_file, 'r') as f:
                try:
                    self.version = json.load(f)
                    logger.info(f"Loaded IOC version: {self.version['version']}")
                except json.JSONDecodeError:
                    logger.error("Failed to parse version file, using default")
        else:
            logger.info("No existing version file, starting with version 1")
            self._save_version()
    
    def _save_iocs(self):
        """Save IOCs to file and update version."""
        with open(self.iocs_file, 'w') as f:
            json.dump(self.iocs, f, indent=2)
        
        # Update version after saving IOCs
        self.version['version'] += 1
        self.version['updated_at'] = int(time.time())
        self.version['hash'] = self._calculate_hash()
        self._save_version()
        
        logger.info(f"Saved {self._count_iocs()} IOCs to storage (version {self.version['version']})")
    
    def _save_version(self):
        """Save version information to file."""
        with open(self.version_file, 'w') as f:
            json.dump(self.version, f, indent=2)
    
    def _calculate_hash(self):
        """Calculate hash of the IOC database for integrity checking."""
        with open(self.iocs_file, 'r') as f:
            content = f.read().encode('utf-8')
            return hashlib.sha256(content).hexdigest()
    
    def _count_iocs(self):
        """Count the total number of IOCs in the database."""
        return (
            len(self.iocs['ip_addresses']) + 
            len(self.iocs['file_hashes']) + 
            len(self.iocs['urls']) + 
            len(self.iocs['process_names'])
        )
    
    def add_ip(self, ip, description="", severity="medium"):
        """Add an IP address to the IOC database.
        
        Args:
            ip (str): IP address to add
            description (str): Description of the threat
            severity (str): Severity level (low, medium, high, critical)
            
        Returns:
            bool: True if added successfully
        """
        if not self._validate_ip(ip):
            logger.error(f"Invalid IP format: {ip}")
            return False
        
        self.iocs['ip_addresses'][ip] = {
            'added_at': int(time.time()),
            'description': description,
            'severity': severity
        }
        
        logger.info(f"Added IP IOC: {ip} ({severity})")
        self._save_iocs()
        return True
    
    def add_file_hash(self, file_hash, hash_type="sha256", description="", severity="medium"):
        """Add a file hash to the IOC database.
        
        Args:
            file_hash (str): File hash to add
            hash_type (str): Hash type (md5, sha1, sha256)
            description (str): Description of the threat
            severity (str): Severity level (low, medium, high, critical)
            
        Returns:
            bool: True if added successfully
        """
        if not self._validate_hash(file_hash, hash_type):
            logger.error(f"Invalid {hash_type} hash format: {file_hash}")
            return False
        
        self.iocs['file_hashes'][file_hash] = {
            'hash_type': hash_type,
            'added_at': int(time.time()),
            'description': description,
            'severity': severity
        }
        
        logger.info(f"Added {hash_type} hash IOC: {file_hash} ({severity})")
        self._save_iocs()
        return True
    
    def add_url(self, url, description="", severity="medium"):
        """Add a URL to the IOC database.
        
        Args:
            url (str): URL to add
            description (str): Description of the threat
            severity (str): Severity level (low, medium, high, critical)
            
        Returns:
            bool: True if added successfully
        """
        # Store URLs in lowercase for case-insensitive matching
        url = url.lower()
        
        self.iocs['urls'][url] = {
            'added_at': int(time.time()),
            'description': description,
            'severity': severity
        }
        
        logger.info(f"Added URL IOC: {url} ({severity})")
        self._save_iocs()
        return True
    
    def add_process_name(self, process_name, description="", severity="medium"):
        """Add a process name to the IOC database.
        
        Args:
            process_name (str): Process name to add
            description (str): Description of the threat
            severity (str): Severity level (low, medium, high, critical)
            
        Returns:
            bool: True if added successfully
        """
        # Store process names in lowercase for case-insensitive matching
        process_name = process_name.lower()
        
        self.iocs['process_names'][process_name] = {
            'added_at': int(time.time()),
            'description': description,
            'severity': severity
        }
        
        logger.info(f"Added process name IOC: {process_name} ({severity})")
        self._save_iocs()
        return True
    
    def remove_ioc(self, ioc_type, value):
        """Remove an IOC from the database.
        
        Args:
            ioc_type (str): Type of IOC (ip, hash, url, process)
            value (str): Value to remove
            
        Returns:
            bool: True if removed successfully
        """
        if ioc_type == 'ip' and value in self.iocs['ip_addresses']:
            del self.iocs['ip_addresses'][value]
            logger.info(f"Removed IP IOC: {value}")
            self._save_iocs()
            return True
        elif ioc_type == 'hash' and value in self.iocs['file_hashes']:
            del self.iocs['file_hashes'][value]
            logger.info(f"Removed hash IOC: {value}")
            self._save_iocs()
            return True
        elif ioc_type == 'url' and value in self.iocs['urls']:
            del self.iocs['urls'][value]
            logger.info(f"Removed URL IOC: {value}")
            self._save_iocs()
            return True
        elif ioc_type == 'process' and value in self.iocs['process_names']:
            del self.iocs['process_names'][value]
            logger.info(f"Removed process IOC: {value}")
            self._save_iocs()
            return True
        else:
            logger.warning(f"IOC not found: {ioc_type}:{value}")
            return False
    
    def get_all_iocs(self):
        """Get all IOCs in the database.
        
        Returns:
            dict: All IOCs in the database
        """
        return {
            'iocs': self.iocs,
            'version': self.version['version'],
            'updated_at': self.version['updated_at'],
            'count': self._count_iocs()
        }
    
    def get_iocs_by_type(self, ioc_type):
        """Get IOCs of a specific type.
        
        Args:
            ioc_type (str): Type of IOC (ip, hash, url, process)
            
        Returns:
            dict: IOCs of the specified type
        """
        if ioc_type == 'ip':
            return self.iocs['ip_addresses']
        elif ioc_type == 'hash':
            return self.iocs['file_hashes']
        elif ioc_type == 'url':
            return self.iocs['urls']
        elif ioc_type == 'process':
            return self.iocs['process_names']
        else:
            logger.warning(f"Unknown IOC type: {ioc_type}")
            return {}
    
    def get_version_info(self):
        """Get version information for the IOC database.
        
        Returns:
            dict: Version information
        """
        return self.version
    
    def import_iocs_from_file(self, file_path):
        """Import IOCs from a JSON file.
        
        Args:
            file_path (str): Path to the JSON file
            
        Returns:
            dict: Import results
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            results = {
                'imported': 0,
                'failed': 0,
                'duplicates': 0
            }
            
            # Import IP addresses
            if 'ip_addresses' in data:
                for ip, info in data['ip_addresses'].items():
                    if ip in self.iocs['ip_addresses']:
                        results['duplicates'] += 1
                    elif self.add_ip(ip, info.get('description', ''), info.get('severity', 'medium')):
                        results['imported'] += 1
                    else:
                        results['failed'] += 1
            
            # Import file hashes
            if 'file_hashes' in data:
                for file_hash, info in data['file_hashes'].items():
                    if file_hash in self.iocs['file_hashes']:
                        results['duplicates'] += 1
                    elif self.add_file_hash(file_hash, info.get('hash_type', 'sha256'), 
                                          info.get('description', ''), info.get('severity', 'medium')):
                        results['imported'] += 1
                    else:
                        results['failed'] += 1
            
            # Import URLs
            if 'urls' in data:
                for url, info in data['urls'].items():
                    if url in self.iocs['urls']:
                        results['duplicates'] += 1
                    elif self.add_url(url, info.get('description', ''), info.get('severity', 'medium')):
                        results['imported'] += 1
                    else:
                        results['failed'] += 1
            
            # Import process names
            if 'process_names' in data:
                for process, info in data['process_names'].items():
                    if process in self.iocs['process_names']:
                        results['duplicates'] += 1
                    elif self.add_process_name(process, info.get('description', ''), info.get('severity', 'medium')):
                        results['imported'] += 1
                    else:
                        results['failed'] += 1
            
            logger.info(f"Import results: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to import IOCs: {e}")
            return {
                'imported': 0,
                'failed': 0,
                'duplicates': 0,
                'error': str(e)
            }
    
    def export_iocs_to_file(self, file_path):
        """Export IOCs to a JSON file.
        
        Args:
            file_path (str): Path to save the JSON file
            
        Returns:
            bool: True if exported successfully
        """
        try:
            with open(file_path, 'w') as f:
                json.dump(self.iocs, f, indent=2)
            
            logger.info(f"Exported {self._count_iocs()} IOCs to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export IOCs: {e}")
            return False
    
    def _validate_ip(self, ip):
        """Validate IP address format.
        
        Args:
            ip (str): IP address to validate
            
        Returns:
            bool: True if valid
        """
        # Simple validation - improve as needed
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        
        for part in parts:
            try:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            except ValueError:
                return False
        
        return True
    
    def _validate_hash(self, file_hash, hash_type):
        """Validate hash format.
        
        Args:
            file_hash (str): Hash to validate
            hash_type (str): Hash type
            
        Returns:
            bool: True if valid
        """
        if hash_type == 'md5':
            return len(file_hash) == 32 and all(c in '0123456789abcdefABCDEF' for c in file_hash)
        elif hash_type == 'sha1':
            return len(file_hash) == 40 and all(c in '0123456789abcdefABCDEF' for c in file_hash)
        elif hash_type == 'sha256':
            return len(file_hash) == 64 and all(c in '0123456789abcdefABCDEF' for c in file_hash)
        else:
            return False 