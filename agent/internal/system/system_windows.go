package system

import (
	"fmt"
	"net"
	"os"
	"time"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/mem"
)

// AgentVersion represents the current version of the agent
const AgentVersion = "1.0.0"

// MachineInfo contains system information about the Windows machine
type MachineInfo struct {
	Hostname     string
	OSVersion    string
	CPUInfo      string
	TotalMemory  int64
	FreeMemory   int64
	IPAddress    string
	MACAddress   string
	Disks        []DiskInfo
	AgentVersion string
	Timestamp    int64
}

// DiskInfo contains information about a disk
type DiskInfo struct {
	DriveLetter string
	FileSystem  string
	TotalSize   int64
	FreeSpace   int64
}

// GetHostname returns the hostname of the current machine
func GetHostname() (string, error) {
	return os.Hostname()
}

// GetMachineInfo collects system information from a Windows machine
func GetMachineInfo() (*MachineInfo, error) {
	// Get hostname
	hostname, err := GetHostname()
	if err != nil {
		return nil, fmt.Errorf("failed to get hostname: %v", err)
	}

	// Get OS information
	hostInfo, err := host.Info()
	if err != nil {
		return nil, fmt.Errorf("failed to get host info: %v", err)
	}
	osVersion := fmt.Sprintf("%s %s (%s)", hostInfo.Platform, hostInfo.PlatformVersion, hostInfo.PlatformFamily)

	// Get CPU information
	cpuInfoStats, err := cpu.Info()
	if err != nil {
		return nil, fmt.Errorf("failed to get CPU info: %v", err)
	}
	var cpuInfo string
	if len(cpuInfoStats) > 0 {
		cpuInfo = fmt.Sprintf("%s (%d cores)", cpuInfoStats[0].ModelName, cpuInfoStats[0].Cores)
	}

	// Get memory information
	memInfo, err := mem.VirtualMemory()
	if err != nil {
		return nil, fmt.Errorf("failed to get memory info: %v", err)
	}

	// Get network information
	ipAddress, macAddress, err := getNetworkInfo()
	if err != nil {
		return nil, fmt.Errorf("failed to get network info: %v", err)
	}

	// Get disk information
	disks, err := getDiskInfo()
	if err != nil {
		return nil, fmt.Errorf("failed to get disk info: %v", err)
	}

	return &MachineInfo{
		Hostname:     hostname,
		OSVersion:    osVersion,
		CPUInfo:      cpuInfo,
		TotalMemory:  int64(memInfo.Total),
		FreeMemory:   int64(memInfo.Free),
		IPAddress:    ipAddress,
		MACAddress:   macAddress,
		Disks:        disks,
		AgentVersion: AgentVersion,
		Timestamp:    time.Now().Unix(),
	}, nil
}

// getNetworkInfo returns the IP and MAC address of the primary network interface
func getNetworkInfo() (string, string, error) {
	interfaces, err := net.Interfaces()
	if err != nil {
		return "", "", err
	}

	for _, iface := range interfaces {
		// Skip loopback and interfaces that are down
		if iface.Flags&net.FlagLoopback != 0 || iface.Flags&net.FlagUp == 0 {
			continue
		}

		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}

		for _, addr := range addrs {
			// Check if the address is an IP network
			switch v := addr.(type) {
			case *net.IPNet:
				ip := v.IP
				if ip.To4() != nil && !ip.IsLoopback() {
					return ip.String(), iface.HardwareAddr.String(), nil
				}
			}
		}
	}

	return "", "", fmt.Errorf("no suitable network interface found")
}

// getDiskInfo returns information about all disks
func getDiskInfo() ([]DiskInfo, error) {
	partitions, err := disk.Partitions(false)
	if err != nil {
		return nil, err
	}

	var disks []DiskInfo
	for _, partition := range partitions {
		usage, err := disk.Usage(partition.Mountpoint)
		if err != nil {
			continue
		}

		diskInfo := DiskInfo{
			DriveLetter: partition.Device,
			FileSystem:  partition.Fstype,
			TotalSize:   int64(usage.Total),
			FreeSpace:   int64(usage.Free),
		}
		disks = append(disks, diskInfo)
	}

	return disks, nil
} 