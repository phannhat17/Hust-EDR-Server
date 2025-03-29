package services

import (
	"context"
	"fmt"
	"log"
	"time"

	pb "github.com/hustonpi/edr-agent/proto"
)

// AgentServer implements the AgentService gRPC service
type AgentServer struct {
	pb.UnimplementedAgentServiceServer
	connectedAgents map[string]*AgentInfo
}

type AgentInfo struct {
	Hostname    string
	IPAddress   string
	LastSeen    time.Time
	OSVersion   string
	AgentVersion string
}

// NewAgentServer creates a new instance of AgentServer
func NewAgentServer() *AgentServer {
	return &AgentServer{
		connectedAgents: make(map[string]*AgentInfo),
	}
}

// SendMachineInfo handles machine information sent by agents
func (s *AgentServer) SendMachineInfo(ctx context.Context, req *pb.MachineInfoRequest) (*pb.MachineInfoResponse, error) {
	log.Printf("Received machine info from agent: %s (%s)", req.Hostname, req.IpAddress)
	
	// Store or update agent information
	s.connectedAgents[req.MacAddress] = &AgentInfo{
		Hostname:     req.Hostname,
		IPAddress:    req.IpAddress,
		LastSeen:     time.Unix(req.Timestamp, 0),
		OSVersion:    req.OsVersion,
		AgentVersion: req.AgentVersion,
	}
	
	// Log disk information
	for _, disk := range req.Disks {
		log.Printf("Disk %s: %s, Total: %d bytes, Free: %d bytes", 
			disk.DriveLetter, disk.FileSystem, disk.TotalSize, disk.FreeSpace)
	}
	
	return &pb.MachineInfoResponse{
		Success: true,
		Message: fmt.Sprintf("Successfully received machine info from %s", req.Hostname),
	}, nil
}

// GetConnectedAgents returns a list of currently connected agents
func (s *AgentServer) GetConnectedAgents() []*AgentInfo {
	var agents []*AgentInfo
	
	// Remove agents that haven't been seen in 10 minutes
	threshold := time.Now().Add(-10 * time.Minute)
	
	for macAddr, agent := range s.connectedAgents {
		if agent.LastSeen.Before(threshold) {
			delete(s.connectedAgents, macAddr)
			continue
		}
		agents = append(agents, agent)
	}
	
	return agents
} 