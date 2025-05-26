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
	"agent/ioc"
	"agent/blocker"
)

// CommandHandler handles incoming commands from the server
type CommandHandler struct {
	client     *EDRClient
	iocManager *ioc.Manager
	scanner    *ioc.Scanner
	blocker    *blocker.Blocker
}

// NewCommandHandler creates a new command handler
func NewCommandHandler(client *EDRClient) *CommandHandler {
	// Create IOC manager
	iocManager := ioc.NewManager(filepath.Join(client.dataDir, "iocs"))
	
	// Load existing IOCs
	if err := iocManager.LoadFromFile(); err != nil {
		log.Printf("Warning: failed to load IOCs: %v", err)
	}
	
	// Create blocker instance
	blockerInstance := blocker.NewBlocker(client.config, client.dataDir)
	
	return &CommandHandler{
		client:     client,
		iocManager: iocManager,
		blocker:    blockerInstance,
	}
}

// HandleCommand processes a command and returns the result
func (h *CommandHandler) HandleCommand(ctx context.Context, cmd *pb.Command) *pb.CommandResult {
	startTime := time.Now()
	

	
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
		message, err = h.handleDeleteFile(cmd.Params)
	case pb.CommandType_KILL_PROCESS:
		message, err = h.handleKillProcess(cmd.Params)
	case pb.CommandType_KILL_PROCESS_TREE:
		message, err = h.handleKillProcessTree(cmd.Params)
	case pb.CommandType_BLOCK_IP:
		message, err = h.handleBlockIP(cmd.Params)
	case pb.CommandType_BLOCK_URL:
		message, err = h.handleBlockURL(cmd.Params)
	case pb.CommandType_NETWORK_ISOLATE:
		message, err = h.handleNetworkIsolate(cmd.Params)
	case pb.CommandType_NETWORK_RESTORE:
		message, err = h.handleNetworkRestore(cmd.Params)
	case pb.CommandType_UPDATE_IOCS:
		// Updates now come directly through the command stream
		message = "UPDATE_IOCS command acknowledged. IOC data will be received through the command stream."
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

// GetIOCManager returns the IOC manager instance
func (h *CommandHandler) GetIOCManager() *ioc.Manager {
	return h.iocManager
}

// SetScanner sets the IOC scanner instance
func (h *CommandHandler) SetScanner(scanner *ioc.Scanner) {
	h.scanner = scanner
}

// GetScanner returns the IOC scanner instance
func (h *CommandHandler) GetScanner() *ioc.Scanner {
	return h.scanner
}

// ReportIOCMatch sends an IOC match report to the server
func (h *CommandHandler) ReportIOCMatch(ctx context.Context, iocType pb.IOCType, iocValue string, 
	matchedValue string, matchContext string, severity string) error {
	
	reportID := fmt.Sprintf("%s-%d", h.client.agentID, time.Now().UnixNano())
	
	// Determine action taken based on the context message
	var actionTaken pb.CommandType = pb.CommandType_UNKNOWN
	actionSuccess := false
	actionMessage := ""
	
	// Check for specific messages that indicate an action was taken
	// For IP blocking
	if iocType == pb.IOCType_IOC_IP && strings.Contains(matchContext, "IP automatically blocked") {
		actionTaken = pb.CommandType_BLOCK_IP
		actionSuccess = true
		actionMessage = fmt.Sprintf("Successfully blocked IP %s using Windows Firewall", matchedValue)
	}
	
	// For URL blocking
	if iocType == pb.IOCType_IOC_URL && strings.Contains(matchContext, "URL blocked by adding domain") {
		actionTaken = pb.CommandType_BLOCK_URL
		actionSuccess = true
		actionMessage = fmt.Sprintf("Successfully blocked URL %s", matchedValue)
	}
	
	// For file deletion after hash match
	if iocType == pb.IOCType_IOC_HASH && strings.Contains(matchContext, "Malicious file") {
		if strings.Contains(matchContext, "deleted: true") {
			actionTaken = pb.CommandType_DELETE_FILE
			actionSuccess = true
			actionMessage = "Successfully deleted malicious file"
		}
	}
	
	report := &pb.IOCMatchReport{
		ReportId:       reportID,
		AgentId:        h.client.agentID,
		Timestamp:      time.Now().Unix(),
		Type:           iocType,
		IocValue:       iocValue,
		MatchedValue:   matchedValue,
		Context:        matchContext,
		Severity:       severity,
		ActionTaken:    actionTaken,
		ActionSuccess:  actionSuccess,
		ActionMessage:  actionMessage,
	}
	
	log.Printf("Reporting IOC match: %s - %s (severity: %s)", pb.IOCType_name[int32(iocType)], iocValue, severity)
	if actionTaken != pb.CommandType_UNKNOWN {
		log.Printf("Action reported: %s (success: %v)", pb.CommandType_name[int32(actionTaken)], actionSuccess)
	}
	
	// Send report to server
	resp, err := h.client.edrClient.ReportIOCMatch(ctx, report)
	if err != nil {
		log.Printf("Failed to report IOC match: %v", err)
		return err
	}
	
	log.Printf("IOC match report acknowledged: %s", resp.Message)
	
	// Check if server requested additional action
	if resp.PerformAdditionalAction && resp.AdditionalAction != pb.CommandType_UNKNOWN {
		log.Printf("Server requested additional action: %s", pb.CommandType_name[int32(resp.AdditionalAction)])
		
		// Create a command to execute locally
		cmd := &pb.Command{
			CommandId: fmt.Sprintf("%s-auto-%d", reportID, time.Now().UnixNano()),
			AgentId:   h.client.agentID,
			Timestamp: time.Now().Unix(),
			Type:      resp.AdditionalAction,
			Params:    resp.ActionParams,
		}
		
		// Execute the command
		result := h.HandleCommand(ctx, cmd)
		
		// Update the report with the action taken
		report.ActionTaken = resp.AdditionalAction
		report.ActionSuccess = result.Success
		report.ActionMessage = result.Message
		
		// Send updated report
		_, err = h.client.edrClient.ReportIOCMatch(ctx, report)
		if err != nil {
			log.Printf("Failed to report IOC action result: %v", err)
		}
	}
	
	return nil
}

// handleDeleteFile deletes a file at the specified path
func (h *CommandHandler) handleDeleteFile(params map[string]string) (string, error) {
	path, ok := params["path"]
	if !ok {
		log.Printf("ERROR: Missing required parameter 'path' in DELETE_FILE command")
		return "", fmt.Errorf("missing required parameter 'path'")
	}
	
	log.Printf("Attempting to delete file at path: %s", path)
	
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
		return "", fmt.Errorf("file not found: %s", path)
	} else if err != nil {
		log.Printf("ERROR: Failed to check file status: %v", err)
		return "", fmt.Errorf("failed to check file status: %v", err)
	}
	
	log.Printf("File exists, size: %d bytes, isDir: %v", fileInfo.Size(), fileInfo.IsDir())
	
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
	// First check if we have a PID
	pidStr, hasPid := params["pid"]
	
	// If not PID, check if we have a process name
	processName, hasProcessName := params["process_name"]
	
	if !hasPid && !hasProcessName {
		return "", fmt.Errorf("missing required parameter: either 'pid' or 'process_name'")
	}

	// If we have a process name but no PID, try to find the PID
	if !hasPid && hasProcessName {
		log.Printf("Finding PID for process name: %s", processName)
		pid, err := h.findProcessIDByName(processName)
		if err != nil {
			return "", fmt.Errorf("failed to find process %s: %v", processName, err)
		}
		pidStr = fmt.Sprintf("%d", pid)
		log.Printf("Found PID %s for process %s", pidStr, processName)
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

	return fmt.Sprintf("Process %d killed successfully", pid), nil
}

// findProcessIDByName finds a process ID by process name
func (h *CommandHandler) findProcessIDByName(name string) (int, error) {
	var cmd *exec.Cmd
	
	// Use TASKLIST on Windows
	cmd = exec.Command("tasklist", "/FI", fmt.Sprintf("IMAGENAME eq %s", name), "/NH", "/FO", "CSV")
	
	output, err := cmd.Output()
	if err != nil {
		return 0, fmt.Errorf("failed to execute process list command: %v", err)
	}
	
	// Parse Windows TASKLIST output (CSV format)
	lines := strings.Split(string(output), "\n")
	for _, line := range lines {
		if strings.Contains(line, name) {
			// Parse CSV line
			parts := strings.Split(line, ",")
			if len(parts) >= 2 {
				// Remove quotes from process name and PID
				processName := strings.Trim(parts[0], "\"")
				pidStr := strings.Trim(parts[1], "\"")
				
				if strings.EqualFold(processName, name) {
					pid, err := strconv.Atoi(pidStr)
					if err == nil {
						return pid, nil
					}
				}
			}
		}
	}
	
	return 0, fmt.Errorf("process '%s' not found", name)
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

	// Use TASKKILL on Windows with /T flag for tree kill
	cmd := exec.Command("taskkill", "/F", "/T", "/PID", pidStr)

	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to kill process tree: %v, output: %s", err, string(output))
	}

	return fmt.Sprintf("Process tree for PID %d killed successfully", pid), nil
}

// handleBlockIP blocks an IP address
func (h *CommandHandler) handleBlockIP(params map[string]string) (string, error) {
	ip, ok := params["ip"]
	if !ok {
		return "", fmt.Errorf("missing required parameter 'ip'")
	}

	// Use the centralized blocker
	err := h.blocker.BlockIP(ip)
	if err != nil {
		return "", fmt.Errorf("failed to block IP %s: %v", ip, err)
	}

	return fmt.Sprintf("IP %s blocked successfully (inbound and outbound)", ip), nil
}

// handleBlockURL blocks a URL
func (h *CommandHandler) handleBlockURL(params map[string]string) (string, error) {
	url, ok := params["url"]
	if !ok {
		return "", fmt.Errorf("missing required parameter 'url'")
	}

	// Use the centralized blocker
	err := h.blocker.BlockURL(url)
	if err != nil {
		return "", fmt.Errorf("failed to block URL %s: %v", url, err)
	}

	return fmt.Sprintf("URL %s blocked successfully", url), nil
}

// handleNetworkIsolate isolates the host from the network
func (h *CommandHandler) handleNetworkIsolate(params map[string]string) (string, error) {
	allowedIPs := params["allowed_ips"]
	
	// Always ensure the server IP is in allowed IPs
	serverIP := h.client.serverAddress
	if serverIP != "" {
		// Extract IP from server address (remove port)
		if strings.Contains(serverIP, ":") {
			serverIP = strings.Split(serverIP, ":")[0]
		}
		
		if allowedIPs == "" {
			allowedIPs = serverIP
		} else if !strings.Contains(allowedIPs, serverIP) {
			allowedIPs = allowedIPs + "," + serverIP
		}
	}

	// Use Windows Firewall to isolate
	// First, block all inbound connections
	inboundCmd := exec.Command("netsh", "advfirewall", "set", "allprofiles", "firewallpolicy", "blockinbound,blockoutbound")
	_, err := inboundCmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to set firewall policy: %v", err)
	}
	
	// Then add rules for allowed IPs
	if allowedIPs != "" {
		allowedIPList := strings.Split(allowedIPs, ",")
		for _, ip := range allowedIPList {
			ip = strings.TrimSpace(ip)
			if ip == "" {
				continue
			}
			
			// Allow inbound connections from allowed IP
			inCmd := exec.Command("netsh", "advfirewall", "firewall", "add", "rule", 
				fmt.Sprintf("name=EDR-Allow-%s-In", ip), "dir=in", "action=allow", fmt.Sprintf("remoteip=%s", ip))
			_, err := inCmd.CombinedOutput()
			if err != nil {
				log.Printf("WARNING: Failed to add inbound rule for %s: %v", ip, err)
			}
			
			// Allow outbound connections to allowed IP
			outCmd := exec.Command("netsh", "advfirewall", "firewall", "add", "rule", 
				fmt.Sprintf("name=EDR-Allow-%s-Out", ip), "dir=out", "action=allow", fmt.Sprintf("remoteip=%s", ip))
			_, err = outCmd.CombinedOutput()
			if err != nil {
				log.Printf("WARNING: Failed to add outbound rule for %s: %v", ip, err)
			}
		}
	}

	return "Network isolation activated successfully", nil
}

// handleNetworkRestore restores network connectivity
func (h *CommandHandler) handleNetworkRestore(params map[string]string) (string, error) {
	// Use Windows Firewall to restore
	// Reset firewall settings
	resetCmd := exec.Command("netsh", "advfirewall", "reset")
	_, err := resetCmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to reset firewall: %v", err)
	}
	
	// Reset firewall policy
	policyCmd := exec.Command("netsh", "advfirewall", "set", "allprofiles", "firewallpolicy", "blockinbound,allowoutbound")
	_, err = policyCmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to set firewall policy: %v", err)
	}
	
	// Delete EDR firewall rules
	deleteRulesCmd := exec.Command("cmd", "/C", "for /f \"tokens=*\" %i in ('netsh advfirewall firewall show rule name^=EDR* ^| findstr \"Rule Name:\"') do netsh advfirewall firewall delete rule name=\"%i\"")
	_, err = deleteRulesCmd.CombinedOutput()
	if err != nil {
		log.Printf("WARNING: Failed to delete EDR firewall rules: %v", err)
	}

	return "Network connectivity restored successfully", nil
}