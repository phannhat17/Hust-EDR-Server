# Logging System Documentation

The EDR server implements a modular logging system that writes different types of logs to separate files. This approach makes it easier to debug specific components and monitor the system's behavior.

## Log File Structure

All logs are stored in the `LOG_DIR` directory (configured in `.env` or defaults to `backend/logs/`). The following log files are created:

| Log File | Content |
|----------|---------|
| `app.log` | Main application logs |
| `api.log` | API endpoint access and operations |
| `grpc.log` | gRPC server interactions with agents |
| `elastalert.log` | ElastAlert rule processing and alert handling |
| `auto_response.log` | Auto-response actions and execution details |
| `db.log` | Database interactions |
| `error.log` | All error-level logs from all components |

## Log Rotation

Each log file is automatically rotated when it reaches 10MB in size. Up to 5 backup files are kept for each log file (e.g., `app.log.1`, `app.log.2`, etc.).

## Log Levels

The global log level is set using the `LOG_LEVEL` environment variable in the `.env` file. Valid values are:

- `DEBUG`: Detailed debug information
- `INFO`: General operational information (default)
- `WARNING`: Warning events
- `ERROR`: Error events that might still allow the application to continue
- `CRITICAL`: Critical events that may cause the application to terminate

## Log Format

Logs in the console use a standard format:
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

Logs in files use a more detailed format that includes the line number and thread name:
```
%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(filename)s:%(lineno)d - %(message)s
```

## Configuration

You can configure the logging system through environment variables in your `.env` file:

```
LOG_LEVEL=INFO
LOG_DIR=logs
```

## Example Log Output

Here's an example of what you might see in the `auto_response.log` file:

```
2023-06-15 14:32:45,123 - app.elastalert_auto_response - INFO - MainThread - elastalert_auto_response.py:47 - Executing DELETE_FILE command to agent agent_123 with params: {'path': '/tmp/malware.exe'}
2023-06-15 14:32:46,456 - app.elastalert_auto_response - INFO - MainThread - elastalert_auto_response.py:92 - Auto-response command succeeded: DELETE_FILE on agent agent_123
```

## Accessing Logs Programmatically

To log from your Python code, use the named logger corresponding to your component:

```python
import logging

# Get the component-specific logger
logger = logging.getLogger('app.elastalert_auto_response')

# Log at different levels
logger.debug("Detailed debug information")
logger.info("General operational information")
logger.warning("Warning events")
logger.error("Error events")
logger.critical("Critical events")
```

## Console Output

In addition to file logging, INFO-level and above logs are also printed to the console during development, making it easier to debug while working on the application. 