from flask import Blueprint, jsonify
from services.agent_grpc_service import get_connected_agents

agents_bp = Blueprint("agents", __name__)

@agents_bp.route("/agents", methods=["GET"])
def list_agents():
    """
    Get list of connected agents
    ---
    tags:
      - Agents
    responses:
      200:
        description: List of connected agents
    """
    agents = get_connected_agents()
    return jsonify({"agents": agents})

@agents_bp.route("/agents/count", methods=["GET"])
def count_agents():
    """
    Get count of connected agents
    ---
    tags:
      - Agents
    responses:
      200:
        description: Count of connected agents
    """
    agents = get_connected_agents()
    return jsonify({"count": len(agents)})

@agents_bp.route("/agents/<mac_address>", methods=["GET"])
def get_agent(mac_address):
    """
    Get agent details by MAC address
    ---
    tags:
      - Agents
    parameters:
      - name: mac_address
        in: path
        required: true
        type: string
        description: MAC address of the agent
    responses:
      200:
        description: Agent details
      404:
        description: Agent not found
    """
    from services.agent_grpc_service import connected_agents
    
    if mac_address in connected_agents:
        return jsonify(connected_agents[mac_address])
    else:
        return jsonify({"error": "Agent not found"}), 404 