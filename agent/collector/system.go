package collector

import (
	"fmt"
	"net"
	"os"
	"os/user"
	"time"

	"github.com/denisbrodbeck/machineid"
	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/mem"
	pb "agent/proto"
)

// SystemCollector collects system information
type SystemCollector struct {
	// Cache the machine ID to be used as agent ID
	agentID string
}

// NewSystemCollector creates a new system collector
func NewSystemCollector() *SystemCollector {
	collector := &SystemCollector{}
	
	// Generate a machine-specific identifier
	id, err := machineid.ID()
	if err != nil {
		// Fall back to hostname if machine ID can't be obtained
		hostname, _ := os.Hostname()
		id = fmt.Sprintf("agent-%s", hostname)
	}
	
	collector.agentID = id
	return collector
}

// CollectAgentInfo collects basic system information for agent registration
func (s *SystemCollector) CollectAgentInfo() (*pb.AgentInfo, error) {
	// Get hostname
	hostname, err := os.Hostname()
	if err != nil {
		return nil, fmt.Errorf("failed to get hostname: %v", err)
	}

	// Get primary IP address
	ipAddress, macAddress, err := getPrimaryInterface()
	if err != nil {
		return nil, fmt.Errorf("failed to get network information: %v", err)
	}

	// Get current username
	username := getCurrentUsername()

	// Get OS version information
	osInfo, err := host.Info()
	if err != nil {
		return nil, fmt.Errorf("failed to get OS information: %v", err)
	}
	
	// Format OS version
	osVersion := fmt.Sprintf("%s %s (build %s)", osInfo.Platform, osInfo.PlatformVersion, osInfo.KernelVersion)

	return &pb.AgentInfo{
		AgentId:          s.agentID,
		Hostname:         hostname,
		IpAddress:        ipAddress,
		MacAddress:       macAddress,
		Username:         username,
		OsVersion:        osVersion,
		AgentVersion:     "1.0.0", // Hardcoded for now
		RegistrationTime: time.Now().Unix(),
	}, nil
}

// CollectAgentStatus collects current system status
func (s *SystemCollector) CollectAgentStatus(agentID string) (*pb.AgentStatus, error) {
	// Get CPU usage
	cpuUsage, err := getCPUUsage()
	if err != nil {
		return nil, fmt.Errorf("failed to get CPU usage: %v", err)
	}

	// Get memory usage
	memUsage, err := getMemoryUsage()
	if err != nil {
		return nil, fmt.Errorf("failed to get memory usage: %v", err)
	}

	// Get uptime
	uptime, err := getUptime()
	if err != nil {
		return nil, fmt.Errorf("failed to get uptime: %v", err)
	}

	return &pb.AgentStatus{
		AgentId:   agentID,
		Timestamp: time.Now().Unix(),
		Status:    "ONLINE",
		SystemMetrics: &pb.SystemMetrics{
			CpuUsage:    cpuUsage,
			MemoryUsage: memUsage,
			Uptime:      uptime,
		},
	}, nil
}

// Helper functions

// getPrimaryInterface gets the primary network interface IP and MAC addresses
func getPrimaryInterface() (string, string, error) {
	ifaces, err := net.Interfaces()
	if err != nil {
		return "", "", err
	}

	for _, iface := range ifaces {
		// Skip loopback, non-up interfaces, and interfaces without MAC
		if iface.Flags&net.FlagLoopback != 0 || iface.Flags&net.FlagUp == 0 || len(iface.HardwareAddr) == 0 {
			continue
		}

		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}

		for _, addr := range addrs {
			// Check if it's an IP network address
			if ipnet, ok := addr.(*net.IPNet); ok && !ipnet.IP.IsLoopback() {
				// We want IPv4
				if ipnet.IP.To4() != nil {
					return ipnet.IP.String(), iface.HardwareAddr.String(), nil
				}
			}
		}
	}

	return "unknown", "unknown", fmt.Errorf("no suitable network interface found")
}

// getCurrentUsername gets the current user's username
func getCurrentUsername() string {
	currentUser, err := user.Current()
	if err != nil {
		// Fall back to environment variable
		username := os.Getenv("USERNAME")
		if username == "" {
			username = os.Getenv("USER")
		}
		if username == "" {
			return "unknown"
		}
		return username
	}
	return currentUser.Username
}

// getCPUUsage gets the current CPU usage percentage
func getCPUUsage() (float64, error) {
	percentages, err := cpu.Percent(time.Second, false)
	if err != nil {
		return 0, err
	}
	if len(percentages) == 0 {
		return 0, fmt.Errorf("no CPU usage data available")
	}
	return percentages[0], nil
}

// getMemoryUsage gets the current memory usage percentage
func getMemoryUsage() (float64, error) {
	memInfo, err := mem.VirtualMemory()
	if err != nil {
		return 0, err
	}
	return memInfo.UsedPercent, nil
}

// getUptime gets the system uptime in seconds
func getUptime() (int64, error) {
	hostInfo, err := host.Info()
	if err != nil {
		return 0, err
	}
	return int64(hostInfo.Uptime), nil
} 