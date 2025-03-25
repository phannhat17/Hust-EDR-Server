# Working with ElastAlert in the EDR System

## Overview

The EDR system integrates with ElastAlert, a framework for alerting on anomalies, spikes, or other patterns of interest in data stored in Elasticsearch. This document explains how to work with this integration.

## Setup Prerequisites

Before using the ElastAlert integration, you need:

1. A running Elasticsearch instance
2. ElastAlert set up (either on host or in Docker)
3. The EDR Python application configured to connect to both

The simplest setup method is to use the provided `setup_elastalert.sh` script, which configures and starts ElastAlert in Docker:

```bash
./setup_elastalert.sh
```

## Alert Flow

1. **Log Collection**: Logs are collected from endpoints and stored in Elasticsearch
2. **Alert Detection**: ElastAlert periodically queries Elasticsearch based on rule configurations
3. **Alert Generation**: When a rule condition is met, ElastAlert:
   - Creates an alert record in its status index
   - Sends notifications to configured destinations (email, Discord, etc.)
4. **Alert Management**: The EDR system:
   - Reads alerts from the ElastAlert status index
   - Provides a UI for viewing and managing alerts
   - Allows updating alert status and adding analysis notes

## Managing Rules

### Understanding Rule Structure

ElastAlert rules are YAML files that define:

- What to search for in Elasticsearch data
- How often to search
- When to trigger alerts
- Where to send notifications

A basic rule includes:

- `name`: Rule name (required)
- `type`: Rule type (e.g., any, frequency, spike, etc.)
- `index`: Elasticsearch index pattern to search
- `filter`: Query conditions to match events
- `alert`: List of alerter types to use
- Additional configuration specific to the rule type and alerters

### Creating Rules

1. Navigate to the Rules page in the EDR application
2. Click "New Rule"
3. Enter rule details:
   - Rule name
   - YAML configuration

The system validates and saves the rule. ElastAlert automatically loads new rules within a minute.

### Best Practices for Rules

1. **Test thoroughly**: Start with limited scope rules before broadening
2. **Add descriptions**: Include a clear description in each rule
3. **Use realert**: Set appropriate `realert` periods to prevent alert storms
4. **Include context**: Configure alerts to include relevant context for investigation
5. **Tag and categorize**: Use consistent naming and add `priority` and `category` fields

## Alert Status Management

Alerts in the EDR system have a workflow represented by status values:

1. **New**: Initial state for all alerts
2. **In Review**: An analyst has seen the alert and is evaluating it
3. **In Progress**: Active investigation is underway
4. **Resolved**: The alert has been addressed
5. **False Positive**: The alert was determined to be incorrect

### Working with Alerts

1. Navigate to the Alerts page to see all alerts
2. Click "View" on an alert to see details and update status
3. Add analysis notes to document your findings
4. Assign alerts to team members for accountability

## Troubleshooting

### ElastAlert Not Generating Alerts

Check:
1. ElastAlert container/service is running
2. Rule files have correct syntax
3. Rule files are in the correct directory
4. Elasticsearch connection is working
5. ElastAlert logs for errors

```bash
# Check ElastAlert container (if using Docker)
docker logs elastalert
```

### Rules Not Appearing in the UI

Check:
1. `ELASTALERT_RULES_DIR` is set correctly in .env
2. The application has read permissions on the directory
3. Rule files have .yaml extension

### Alerts Not Appearing in the UI

Check:
1. `ELASTALERT_INDEX` is set correctly in .env
2. Elasticsearch connection details are correct
3. The application has permissions to read from the index

## ElastAlert Rule Types

The most common rule types are:

- **any**: Match any documents with the specified filter
- **frequency**: Match when a certain number of events occur in a time period
- **spike**: Match when the volume of events increases or decreases significantly
- **flatline**: Match when the volume of events drops below a threshold
- **new_term**: Match when a new value appears in a field
- **cardinality**: Match when the number of unique values for a field is above/below a threshold

## Additional Resources

- [ElastAlert 2 Documentation](https://elastalert2.readthedocs.io/)
- [Elasticsearch Query DSL](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html) 