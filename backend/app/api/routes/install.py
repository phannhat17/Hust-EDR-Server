import os
from flask import Blueprint, send_file, jsonify, make_response, request

# Create blueprint
install_bp = Blueprint('install', __name__)

# Path to the install_agent_script directory
SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 
                         'install_agent_script')
CERT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 
                         'cert')

# Sysmon routes
@install_bp.route('/sysmon-script', methods=['GET'])
def get_sysmon_script():
    """Serve the Sysmon installation script."""
    script_path = os.path.join(SCRIPT_DIR, 'install_sysmon.ps1')
    return send_file(script_path, mimetype='text/plain')

# Winlogbeat routes
@install_bp.route('/winlogbeat-script', methods=['GET'])
def get_winlogbeat_script():
    """Serve the Winlogbeat installation script."""
    script_path = os.path.join(SCRIPT_DIR, 'install_winlogbeat.ps1')
    return send_file(script_path, mimetype='text/plain')

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

@install_bp.route('/winlogbeat-config', methods=['GET'])
def get_winlogbeat_config():
    """Serve the Winlogbeat configuration file."""
    config_path = os.path.join(SCRIPT_DIR, 'winlogbeat.yml')
    return send_file(config_path, mimetype='text/plain')

@install_bp.route('/kibana-cert', methods=['GET'])
def get_kibana_cert():
    """Serve the first certificate file for Winlogbeat."""
    cert_path = os.path.join(CERT_DIR, 'kibana.crt')
    return send_file(cert_path, mimetype='application/x-x509-ca-cert')

@install_bp.route('/elasticsearch-cert', methods=['GET'])
def get_elasticsearch_cert():
    """Serve the second certificate file for Winlogbeat."""
    cert_path = os.path.join(CERT_DIR, 'elasticsearch.crt')
    return send_file(cert_path, mimetype='application/x-x509-ca-cert')

# Combined Sysmon + Winlogbeat routes
@install_bp.route('/combined-script/<host>', methods=['GET'])
def get_combined_script_with_host(host):
    """Serve the combined installation script with the server host parameter embedded."""
    script_path = os.path.join(SCRIPT_DIR, 'install_combined.ps1')
    with open(script_path, 'r') as f:
        script_content = f.read()
    
    # Modify the script to include the server host parameter
    modified_script = script_content.replace('param(\n    [string]$ServerHost = "localhost:5000"\n)', f'# Server host is embedded: {host}')
    modified_script = modified_script.replace('$ServerHost', f'{host}')
    
    # Return as plain text
    response = make_response(modified_script)
    response.headers['Content-Type'] = 'text/plain'
    return response

@install_bp.route('/', methods=['GET'])
def get_install_info():
    """Provide installation instructions."""
    server_host = request.host
    
    # Combined installation one-liner
    combined_oneliner = f"""powershell -Command "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('http://{server_host}/api/install/combined-script/{server_host}'))" """
    
    response = make_response(combined_oneliner)
    response.headers['Content-Type'] = 'text/plain'
    return response
