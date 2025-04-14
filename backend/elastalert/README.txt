ElastAlert 2 Directory Structure
==============================

This directory contains the configuration and rules for ElastAlert 2, which is used for alerting on Elasticsearch data.

Directory Structure:
------------------
elastalert/
├── config/         # Configuration files
│   └── config.yaml # Main ElastAlert configuration
├── rules/          # Alert rules
│   └── *.yaml      # Rule definition files
└── modules/        # Custom modules
    └── *.py        # Custom rule types and enhancements

Configuration:
-------------
The main configuration file is located at:
- config/config.yaml

This file contains global settings for ElastAlert, including:
- Elasticsearch connection details
- Alert settings
- Rule loading configuration
- Email settings
- Other global parameters

Rules:
------
Alert rules are stored in the rules/ directory as YAML files. Each file defines:
- Rule type and conditions
- Alert actions
- Time windows
- Filter conditions
- Alert messages

Modules:
--------
Custom modules for extending ElastAlert functionality are stored in the modules/ directory.
These can include:
- Custom rule types
- Custom alerts
- Custom enhancements
- Utility functions

Setup:
------
1. Ensure Docker is installed
2. Run the setup script:
   $ ./setup_elastalert.sh

This will:
- Create the directory structure
- Generate the config file
- Start ElastAlert in Docker
- Mount the necessary volumes

Maintenance:
-----------
- Rules can be added/modified in the rules/ directory
- Configuration can be updated in config/config.yaml
- Custom modules can be added to the modules/ directory
- Changes take effect after ElastAlert container restart

Note: The config.yaml file is not tracked in git for security reasons.
Make sure to backup your configuration separately. 