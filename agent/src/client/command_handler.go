package client

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	pb "agent/proto"
)

// CommandHandler handles incoming commands from the server
type CommandHandler struct {
	client *EDRClient
}

// NewCommandHandler creates a new command handler
func NewCommandHandler(client *EDRClient) *CommandHandler {
	return &CommandHandler{
		client: client,
	}
}

// HandleCommand processes a command and returns the result
func (h *CommandHandler) HandleCommand(ctx context.Context, cmd *pb.Command) *pb.CommandResult {
	startTime := time.Now()
	
	// Add more detailed logging about the incoming command
	log.Printf("DEBUG: HandleCommand received command - ID: %s, Type: %d (%s)", 
		cmd.CommandId, cmd.Type, cmd.Type.String())
	log.Printf("DEBUG: Command params dump: %+v", cmd.Params)
	
	result := &pb.CommandResult{
		CommandId:     cmd.CommandId,
		AgentId:       cmd.AgentId,
		ExecutionTime: time.Now().Unix(),
		Success:       false,
		Message:       "",
	}

	var err error
	var message string

	log.Printf("Processing command %s of type %s", cmd.CommandId, cmd.Type.String())

	// Execute command based on type
	switch cmd.Type {
	case pb.CommandType_DELETE_FILE:
		log.Printf("DEBUG: Matched DELETE_FILE type (value: %d), calling handleDeleteFile", int(pb.CommandType_DELETE_FILE))
		message, err = h.handleDeleteFile(cmd.Params)
	case pb.CommandType_KILL_PROCESS:
		log.Printf("DEBUG: Matched KILL_PROCESS type (value: %d)", int(pb.CommandType_KILL_PROCESS))
		message, err = h.handleKillProcess(cmd.Params)
	case pb.CommandType_KILL_PROCESS_TREE:
		log.Printf("DEBUG: Matched KILL_PROCESS_TREE type (value: %d)", int(pb.CommandType_KILL_PROCESS_TREE))
		message, err = h.handleKillProcessTree(cmd.Params)
	case pb.CommandType_BLOCK_IP:
		log.Printf("DEBUG: Matched BLOCK_IP type (value: %d)", int(pb.CommandType_BLOCK_IP))
		message, err = h.handleBlockIP(cmd.Params)
	case pb.CommandType_BLOCK_URL:
		log.Printf("DEBUG: Matched BLOCK_URL type (value: %d)", int(pb.CommandType_BLOCK_URL))
		message, err = h.handleBlockURL(cmd.Params)
	case pb.CommandType_NETWORK_ISOLATE:
		log.Printf("DEBUG: Matched NETWORK_ISOLATE type (value: %d)", int(pb.CommandType_NETWORK_ISOLATE))
		message, err = h.handleNetworkIsolate(cmd.Params)
	case pb.CommandType_NETWORK_RESTORE:
		log.Printf("DEBUG: Matched NETWORK_RESTORE type (value: %d)", int(pb.CommandType_NETWORK_RESTORE))
		message, err = h.handleNetworkRestore(cmd.Params)
	default:
		log.Printf("ERROR: Unknown command type: %d (%s)", int(cmd.Type), cmd.Type.String())
		err = fmt.Errorf("unknown command type: %s", cmd.Type.String())
	}

	// Set result fields
	result.DurationMs = time.Since(startTime).Milliseconds()
	
	if err != nil {
		result.Success = false
		result.Message = fmt.Sprintf("Error: %v", err)
		log.Printf("Command %s failed: %v", cmd.CommandId, err)
	} else {
		result.Success = true
		result.Message = message
		log.Printf("Command %s completed successfully: %s", cmd.CommandId, message)
	}

	return result
}

// handleDeleteFile deletes a file at the specified path
func (h *CommandHandler) handleDeleteFile(params map[string]string) (string, error) {
	path, ok := params["path"]
	if !ok {
		log.Printf("ERROR: Missing required parameter 'path' in DELETE_FILE command")
		return "", fmt.Errorf("missing required parameter 'path'")
	}
	
	log.Printf("Attempting to delete file at path: %s", path)
	
	// Print all parameters received for debugging
	log.Printf("All parameters received: %+v", params)
	
	// Check if path is absolute
	if !filepath.IsAbs(path) {
		log.Printf("WARNING: Path is not absolute, current working directory is: %s", getCurrentDirectory())
		absPath, err := filepath.Abs(path)
		if err != nil {
			log.Printf("ERROR: Failed to get absolute path: %v", err)
		} else {
			log.Printf("INFO: Converted relative path to absolute: %s", absPath)
			path = absPath
		}
	}
	
	// Check if file exists
	fileInfo, err := os.Stat(path)
	if os.IsNotExist(err) {
		log.Printf("ERROR: File not found at path: %s", path)
		
		// Try to list parent directory to see what's available
		parentDir := filepath.Dir(path)
		log.Printf("DEBUG: Checking contents of parent directory: %s", parentDir)
		
		files, err := os.ReadDir(parentDir)
		if err != nil {
			log.Printf("ERROR: Could not read parent directory: %v", err)
		} else {
			log.Printf("DEBUG: Parent directory contents (%d entries):", len(files))
			for i, file := range files {
				if i < 10 { // Limit to first 10 entries to avoid log flooding
					log.Printf("  - %s (isDir: %v)", file.Name(), file.IsDir())
				}
			}
			if len(files) > 10 {
				log.Printf("  - ... and %d more entries", len(files)-10)
			}
		}
		
		return "", fmt.Errorf("file not found: %s", path)
	} else if err != nil {
		log.Printf("ERROR: Failed to check file status: %v", err)
		return "", fmt.Errorf("failed to check file status: %v", err)
	}
	
	log.Printf("File exists, size: %d bytes, isDir: %v", fileInfo.Size(), fileInfo.IsDir())
	
	// Check file permissions before attempting to delete
	log.Printf("DEBUG: File mode: %s", fileInfo.Mode().String())
	
	// Delete the file
	err = os.Remove(path)
	if err != nil {
		log.Printf("ERROR: Failed to delete file: %v", err)
		return "", fmt.Errorf("failed to delete file: %v", err)
	}
	
	log.Printf("SUCCESS: File %s deleted successfully", path)
	return fmt.Sprintf("File %s deleted successfully", path), nil
}

// Helper function to get current directory
func getCurrentDirectory() string {
	dir, err := os.Getwd()
	if err != nil {
		log.Printf("ERROR: Failed to get current directory: %v", err)
		return "unknown"
	}
	return dir
}

// handleKillProcess kills a process by PID
func (h *CommandHandler) handleKillProcess(params map[string]string) (string, error) {
	pidStr, ok := params["pid"]
	if !ok {
		return "", fmt.Errorf("missing required parameter 'pid'")
	}

	// Convert PID to integer
	pid, err := strconv.Atoi(pidStr)
	if err != nil {
		return "", fmt.Errorf("invalid PID format: %v", err)
	}

	// Find the process by PID
	process, err := os.FindProcess(pid)
	if err != nil {
		return "", fmt.Errorf("process not found: %v", err)
	}

	// Kill the process
	err = process.Kill()
	if err != nil {
		return "", fmt.Errorf("failed to kill process: %v", err)
	}

	return fmt.Sprintf("Process with PID %d killed successfully", pid), nil
}

// handleKillProcessTree kills a process and all its children
func (h *CommandHandler) handleKillProcessTree(params map[string]string) (string, error) {
	pidStr, ok := params["pid"]
	if !ok {
		return "", fmt.Errorf("missing required parameter 'pid'")
	}

	// Convert PID to integer
	pid, err := strconv.Atoi(pidStr)
	if err != nil {
		return "", fmt.Errorf("invalid PID format: %v", err)
	}

	// Platform-specific implementation for killing process tree
	var cmd *exec.Cmd
	if isWindows() {
		// Windows - use taskkill
		cmd = exec.Command("taskkill", "/F", "/T", "/PID", pidStr)
	} else {
		// Linux/Unix - use pkill
		cmd = exec.Command("bash", "-c", fmt.Sprintf("pkill -P %d && kill -9 %d", pid, pid))
	}

	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to kill process tree: %v - %s", err, string(output))
	}

	return fmt.Sprintf("Process tree with root PID %d killed successfully", pid), nil
}

// handleBlockIP blocks an IP address using the system firewall
func (h *CommandHandler) handleBlockIP(params map[string]string) (string, error) {
	ip, ok := params["ip"]
	if !ok {
		return "", fmt.Errorf("missing required parameter 'ip'")
	}

	var cmd *exec.Cmd
	if isWindows() {
		// Windows - use netsh
		rule := fmt.Sprintf("Block-%s", ip)
		cmd = exec.Command("netsh", "advfirewall", "firewall", "add", "rule", 
			"name="+rule, "dir=in", "action=block", "remoteip="+ip)
	} else {
		// Linux - use iptables
		cmd = exec.Command("iptables", "-A", "INPUT", "-s", ip, "-j", "DROP")
	}

	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to block IP: %v - %s", err, string(output))
	}

	return fmt.Sprintf("IP address %s blocked successfully", ip), nil
}

// handleBlockURL blocks a URL by adding it to the hosts file
func (h *CommandHandler) handleBlockURL(params map[string]string) (string, error) {
	url, ok := params["url"]
	if !ok {
		return "", fmt.Errorf("missing required parameter 'url'")
	}

	// Extract domain from URL
	domain := url
	if strings.HasPrefix(domain, "http://") {
		domain = domain[7:]
	} else if strings.HasPrefix(domain, "https://") {
		domain = domain[8:]
	}
	domain = strings.Split(domain, "/")[0]

	var hostsFile string
	if isWindows() {
		hostsFile = `C:\Windows\System32\drivers\etc\hosts`
	} else {
		hostsFile = "/etc/hosts"
	}

	// Append to hosts file
	entry := fmt.Sprintf("\n127.0.0.1 %s\n", domain)
	file, err := os.OpenFile(hostsFile, os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return "", fmt.Errorf("failed to open hosts file: %v", err)
	}
	defer file.Close()

	if _, err := file.WriteString(entry); err != nil {
		return "", fmt.Errorf("failed to update hosts file: %v", err)
	}

	return fmt.Sprintf("URL %s blocked by adding to hosts file", url), nil
}

// handleNetworkIsolate isolates the machine from the network
func (h *CommandHandler) handleNetworkIsolate(params map[string]string) (string, error) {
	// Get allowed IPs (optional)
	allowedIPs := params["allowed_ips"]
	
	var cmd *exec.Cmd
	if isWindows() {
		// Windows - create blocking rules for all traffic
		cmd = exec.Command("netsh", "advfirewall", "set", "allprofiles", "state", "on")
		if _, err := cmd.CombinedOutput(); err != nil {
			return "", fmt.Errorf("failed to enable firewall: %v", err)
		}
		
		// Block all outbound connections
		cmd = exec.Command("netsh", "advfirewall", "firewall", "add", "rule", 
			"name=EDR-BlockAll", "dir=out", "action=block", "enable=yes")
		
		// If we have allowed IPs, adjust the rule
		if allowedIPs != "" {
			cmd = exec.Command("netsh", "advfirewall", "firewall", "add", "rule", 
				"name=EDR-AllowSpecific", "dir=out", "action=allow", "remoteip="+allowedIPs)
		}
	} else {
		// Linux - use iptables to block all
		cmd = exec.Command("bash", "-c", `
			iptables -P INPUT DROP
			iptables -P OUTPUT DROP
			iptables -P FORWARD DROP
			iptables -A INPUT -i lo -j ACCEPT
			iptables -A OUTPUT -o lo -j ACCEPT`)
		
		// If we have allowed IPs, adjust the rules
		if allowedIPs != "" {
			for _, ip := range strings.Split(allowedIPs, ",") {
				allowCmd := exec.Command("iptables", "-A", "OUTPUT", "-d", strings.TrimSpace(ip), "-j", "ACCEPT")
				if _, err := allowCmd.CombinedOutput(); err != nil {
					return "", fmt.Errorf("failed to add allow rule for %s: %v", ip, err)
				}
			}
		}
	}

	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to isolate network: %v - %s", err, string(output))
	}

	return "Machine isolated from network successfully", nil
}

// handleNetworkRestore restores network connectivity
func (h *CommandHandler) handleNetworkRestore(params map[string]string) (string, error) {
	var cmd *exec.Cmd
	if isWindows() {
		// Windows - remove isolation rules
		cmd = exec.Command("netsh", "advfirewall", "firewall", "delete", "rule", "name=EDR-BlockAll")
		if _, err := cmd.CombinedOutput(); err != nil {
			return "", fmt.Errorf("failed to remove block rule: %v", err)
		}
		
		cmd = exec.Command("netsh", "advfirewall", "firewall", "delete", "rule", "name=EDR-AllowSpecific")
	} else {
		// Linux - restore default iptables policies
		cmd = exec.Command("bash", "-c", `
			iptables -P INPUT ACCEPT
			iptables -P OUTPUT ACCEPT
			iptables -P FORWARD ACCEPT
			iptables -F`)
	}

	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to restore network: %v - %s", err, string(output))
	}

	return "Network connectivity restored successfully", nil
}

// isWindows returns true if the current OS is Windows
func isWindows() bool {
	return os.PathSeparator == '\\' && os.PathListSeparator == ';'
} 