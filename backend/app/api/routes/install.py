import os
from flask import Blueprint, send_file, jsonify, make_response, request

# Create blueprint
install_bp = Blueprint('install', __name__)

# Path directories
SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 
                         'install_agent_script')
CERT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 
                         'cert')

# Certificate routes
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

@install_bp.route('/winlogbeat-script-with-host/<host>', methods=['GET'])
def get_winlogbeat_script_with_host(host):
    """Serve the Winlogbeat installation script with the server host parameter embedded."""
    script_path = os.path.join(SCRIPT_DIR, 'install_winlogbeat.ps1')
    with open(script_path, 'r') as f:
        script_content = f.read()
    
    # Modify the script to include the server host parameter
    modified_script = script_content.replace('param(\n    [string]$ServerHost = "localhost:5000"\n)', f'# Server host is embedded: {host}')
    modified_script = modified_script.replace('$ServerHost', f'{host}')
    
    # Return as plain text
    response = make_response(modified_script)
    response.headers['Content-Type'] = 'text/plain'
    return response

# EDR agent routes
@install_bp.route('/edr-agent-script', methods=['GET'])
def get_edr_agent_script():
    """Serve the EDR agent installation script."""
    script_path = os.path.join(SCRIPT_DIR, 'install_edr_agent.ps1')
    return send_file(script_path, mimetype='text/plain')

@install_bp.route('/edr-agent-script-with-host/<host>', methods=['GET'])
def get_edr_agent_script_with_host(host):
    """Serve the EDR agent installation script with the gRPC host parameter embedded."""
    script_path = os.path.join(SCRIPT_DIR, 'install_edr_agent.ps1')
    with open(script_path, 'r') as f:
        script_content = f.read()
    
    # Modify the script to include the gRPC host parameter
    modified_script = script_content.replace('param(\n    [string]$gRPCHost = "192.168.133.145:50051"\n)', f'# gRPC host is embedded: {host}')
    modified_script = modified_script.replace('$gRPCHost', f'{host}')
    
    # Return as plain text
    response = make_response(modified_script)
    response.headers['Content-Type'] = 'text/plain'
    return response

@install_bp.route('/', methods=['GET'])
def get_edr_install_oneliner():
    """Generate a one-liner PowerShell command to install the EDR agent."""
    host = request.host
    oneliner = f'powershell -Command "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; Invoke-Expression ((New-Object System.Net.WebClient).DownloadString(\'http://{host}/api/install/edr-agent-script\'))"'
    response = make_response(oneliner)
    response.headers['Content-Type'] = 'text/plain'
    return response

@install_bp.route('/edr-stack-script', methods=['GET'])
def get_edr_stack_script():
    """Serve the complete EDR stack installation script."""
    script_path = os.path.join(SCRIPT_DIR, 'install_edr_stack.ps1')
    return send_file(script_path, mimetype='text/plain')

@install_bp.route('/edr-stack-oneliner', methods=['GET'])
def get_edr_stack_oneliner():
    """Generate a one-liner PowerShell command to install the complete EDR stack."""
    host = request.host
    grpc_host = host.split(':')[0] + ':50051'  # Assume gRPC runs on port 50051
    oneliner = f'powershell -Command "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString(\'http://{host}/api/install/edr-stack-script\')); & ${{function:Install-EDRStack}} -ServerHost \'{host}\' -gRPCHost \'{grpc_host}\'"'
    response = make_response(oneliner)
    response.headers['Content-Type'] = 'text/plain'
    return response

