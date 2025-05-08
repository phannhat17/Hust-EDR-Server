package client

import (
	"fmt"
	"net"
	"os"
	"os/exec"
	"runtime"
	"strings"
)

// getHostname returns the hostname of the system
func getHostname() (string, error) {
	return os.Hostname()
}

// getIPAddress returns the primary IP address of the system
func getIPAddress() (string, error) {
	// Get network interfaces
	interfaces, err := net.Interfaces()
	if err != nil {
		return "", fmt.Errorf("failed to get network interfaces: %v", err)
	}

	// Find non-loopback IPv4 address
	for _, iface := range interfaces {
		// Skip loopback, unconnected, or down interfaces
		if iface.Flags&net.FlagLoopback != 0 || iface.Flags&net.FlagUp == 0 {
			continue
		}

		// Get addresses for interface
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}

		// Find IPv4 address
		for _, addr := range addrs {
			ipNet, ok := addr.(*net.IPNet)
			if ok && !ipNet.IP.IsLoopback() && ipNet.IP.To4() != nil {
				return ipNet.IP.String(), nil
			}
		}
	}

	return "", fmt.Errorf("no suitable IP address found")
}

// getMACAddress returns the MAC address of the primary network interface
func getMACAddress() (string, error) {
	// Get network interfaces
	interfaces, err := net.Interfaces()
	if err != nil {
		return "", fmt.Errorf("failed to get network interfaces: %v", err)
	}

	// Find non-loopback interface with an IPv4 address
	for _, iface := range interfaces {
		// Skip loopback, unconnected, or down interfaces
		if iface.Flags&net.FlagLoopback != 0 || iface.Flags&net.FlagUp == 0 {
			continue
		}

		// Get addresses for interface
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}

		// Check for IPv4 address
		hasIPv4 := false
		for _, addr := range addrs {
			ipNet, ok := addr.(*net.IPNet)
			if ok && !ipNet.IP.IsLoopback() && ipNet.IP.To4() != nil {
				hasIPv4 = true
				break
			}
		}

		if hasIPv4 {
			return iface.HardwareAddr.String(), nil
		}
	}

	return "", fmt.Errorf("no suitable MAC address found")
}

// getUsername returns the current username
func getUsername() (string, error) {
	username := os.Getenv("USER")
	
	// Try USERNAME for Windows
	if username == "" {
		username = os.Getenv("USERNAME")
	}
	
	// If still empty, try platform-specific commands
	if username == "" {
		var cmd *exec.Cmd
		
		if runtime.GOOS == "windows" {
			cmd = exec.Command("whoami")
		} else {
			cmd = exec.Command("id", "-un")
		}
		
		output, err := cmd.Output()
		if err != nil {
			return "", fmt.Errorf("failed to execute username command: %v", err)
		}
		
		username = strings.TrimSpace(string(output))
	}
	
	if username == "" {
		return "", fmt.Errorf("could not determine username")
	}
	
	return username, nil
}

// getOSVersion returns the operating system version
func getOSVersion() (string, error) {
	switch runtime.GOOS {
	case "windows":
		cmd := exec.Command("cmd", "/c", "ver")
		output, err := cmd.Output()
		if err != nil {
			return fmt.Sprintf("Windows %s", runtime.GOARCH), nil
		}
		return strings.TrimSpace(string(output)), nil
		
	case "darwin":
		cmd := exec.Command("sw_vers", "-productVersion")
		output, err := cmd.Output()
		if err != nil {
			return fmt.Sprintf("macOS %s", runtime.GOARCH), nil
		}
		return fmt.Sprintf("macOS %s", strings.TrimSpace(string(output))), nil
		
	case "linux":
		// Try to get distribution info
		if _, err := os.Stat("/etc/os-release"); err == nil {
			cmd := exec.Command("bash", "-c", "source /etc/os-release && echo $PRETTY_NAME")
			output, err := cmd.Output()
			if err == nil {
				return strings.TrimSpace(string(output)), nil
			}
		}
		
		// Fallback to uname
		cmd := exec.Command("uname", "-sr")
		output, err := cmd.Output()
		if err != nil {
			return fmt.Sprintf("Linux %s", runtime.GOARCH), nil
		}
		return strings.TrimSpace(string(output)), nil
		
	default:
		return fmt.Sprintf("%s %s", runtime.GOOS, runtime.GOARCH), nil
	}
} 