#!/usr/bin/env python3
"""
Script to process pending ElastAlert alerts and execute auto-response actions.
This can be run manually or scheduled as a cron job.
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.elastalert import ElastAlertClient
from app.grpc.server import EDRServicer
from app.config.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('auto_response.log')
    ]
)

logger = logging.getLogger('auto_response')

def process_alerts(limit=20, dry_run=False, reprocess=False):
    """Process pending alerts and execute auto-response actions.
    
    Args:
        limit (int): Maximum number of alerts to process
        dry_run (bool): If True, do not execute actions, just report
        reprocess (bool): If True, include already processed alerts
        
    Returns:
        dict: Summary of processing results
    """
    # Initialize gRPC server servicer (needed for commands)
    from app.grpc.server import EDRServicer
    grpc_servicer = EDRServicer()
    
    # Create ElastAlert client with gRPC servicer
    client = ElastAlertClient(grpc_servicer)
    
    # If dry run, modify the auto_response_handler to not execute commands
    if dry_run:
        logger.info("Running in dry-run mode - no actions will be executed")
        client.auto_response_handler.execute_commands = False
    
    # Process pending alerts
    logger.info(f"Processing up to {limit} pending alerts{' (including previously processed)' if reprocess else ''}...")
    results = client.process_pending_alerts(limit, include_processed=reprocess)
    
    # Log results
    logger.info(f"Alert processing complete: processed={results.get('processed', 0)}, "
                f"success={results.get('success', 0)}, failed={results.get('failed', 0)}")
    
    return results

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Process ElastAlert alerts and execute auto-response actions')
    parser.add_argument('--limit', type=int, default=20, help='Maximum number of alerts to process')
    parser.add_argument('--dry-run', action='store_true', help='Do not execute actions, just report')
    parser.add_argument('--reprocess', action='store_true', help='Process previously handled alerts again')
    parser.add_argument('--output', type=str, help='Output file for results (JSON format)')
    args = parser.parse_args()
    
    try:
        # Process alerts
        results = process_alerts(args.limit, args.dry_run, args.reprocess)
        
        # Print results
        print(json.dumps(results, indent=2))
        
        # Save results to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
                logger.info(f"Results saved to {args.output}")
        
        # Exit with error code if no alerts were processed
        if results.get('processed', 0) == 0 and 'error' in results:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error processing alerts: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main() 