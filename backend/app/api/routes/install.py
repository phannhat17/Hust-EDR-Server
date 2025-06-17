import os
from flask import Blueprint, send_file, jsonify, make_response, request
from app.config.config import config

# Create blueprint
install_bp = Blueprint('install', __name__)

# Path directories
SCRIPT_DIR = config.SCRIPT_DIR
CERT_DIR = config.CERT_DIR

# Certificate routes
@install_bp.route('/ca-cert', methods=['GET'])
def get_ca_cert():
    """Serve the CA certificate file."""
    cert_path = os.path.join(CERT_DIR, 'ca.crt')
    return send_file(cert_path, mimetype='application/x-x509-ca-cert')

@install_bp.route('/kibana-cert', methods=['GET'])
def get_kibana_cert():
    """Serve the Kibana certificate file."""
    cert_path = os.path.join(CERT_DIR, 'kibana.crt')
    return send_file(cert_path, mimetype='application/x-x509-ca-cert')

@install_bp.route('/elasticsearch-cert', methods=['GET'])
def get_elasticsearch_cert():
    """Serve the Elasticsearch certificate file."""
    cert_path = os.path.join(CERT_DIR, 'elasticsearch.crt')
    return send_file(cert_path, mimetype='application/x-x509-ca-cert')

# Sysmon routes
@install_bp.route('/sysmon-script', methods=['GET'])
def get_sysmon_script():
    """Serve the Sysmon installation script."""
    script_path = os.path.join(SCRIPT_DIR, 'install_sysmon.ps1')
    return send_file(script_path, mimetype='text/plain')

# Winlogbeat routes
@install_bp.route('/winlogbeat-config', methods=['GET'])
def get_winlogbeat_config():
    """Serve the Winlogbeat configuration file."""
    config_path = os.path.join(SCRIPT_DIR, 'winlogbeat.yml')
    return send_file(config_path, mimetype='text/plain')

@install_bp.route('/winlogbeat-script', methods=['GET'])
def get_winlogbeat_script_with_host():
    """Serve the Winlogbeat installation script with the server host parameter embedded."""
    host = request.args.get('host', 'localhost')

    script_path = os.path.join(SCRIPT_DIR, 'install_winlogbeat.ps1')
    with open(script_path, 'r') as f:
        script_content = f.read()
    
    # Modify the script to include the server host parameter
    modified_script = script_content.replace(
        'param(\n    [string]$ServerHost = "localhost:5000"',
        f'param(\n    [string]$ServerHost = "{host}"'
    )
    
    # Return as plain text
    response = make_response(modified_script)
    response.headers['Content-Type'] = 'text/plain'
    return response

# EDR agent routes
@install_bp.route('/edr-agent-script', methods=['GET'])
def get_edr_agent_script_with_params():
    """Serve the EDR agent installation script with the gRPC host and port parameters embedded."""
    # Get host and port from query parameters
    grpc_host = request.args.get('grpc_host', 'localhost:50051')
    server_host = request.args.get('server_host', 'localhost:5000')
    
    script_path = os.path.join(SCRIPT_DIR, 'install_edr_agent.ps1')
    with open(script_path, 'r') as f:
        script_content = f.read()
    
    # Modify the script to include the gRPC host parameter
    # Find and replace only the default value while preserving the variable name
    modified_script = script_content.replace(
        'param(\n    [string]$gRPCHost = "localhost:50051",\n    [string]$ServerHost = "localhost:5000"',
        f'param(\n    [string]$gRPCHost = "{grpc_host}",\n    [string]$ServerHost = "{server_host}"'
    )
    
    # Return as plain text
    response = make_response(modified_script)
    response.headers['Content-Type'] = 'text/plain'
    return response

@install_bp.route('/edr-agent-binary', methods=['GET'])
def get_edr_agent_binary():
    """Serve the EDR agent executable file for direct download."""
    binary_path = os.path.join(SCRIPT_DIR, 'edr-agent.exe')
    
    # Verify the file exists
    if not os.path.exists(binary_path):
        return jsonify({"error": "Agent binary not found"}), 404
    
    # Send the file with appropriate headers for download
    return send_file(
        binary_path,
        mimetype='application/octet-stream',
        as_attachment=True,
        download_name='edr-agent.exe'
    )

@install_bp.route('/edr-stack-script', methods=['GET'])
def get_edr_stack_script():
    """Serve the complete EDR stack installation script."""
    script_path = os.path.join(SCRIPT_DIR, 'install_edr_stack.ps1')
    return send_file(script_path, mimetype='text/plain')

@install_bp.route('/', methods=['GET'])
def get_edr_install_oneliner():
    """Generate a one-liner PowerShell command to install the complete EDR stack."""
    host = request.host
    oneliner = f'powershell -Command "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString(\'http://{host}/api/install/edr-stack-script\'))"'
    response = make_response(oneliner)
    response.headers['Content-Type'] = 'text/plain'
    return response
