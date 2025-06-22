// +build windows

package ioc

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

// SysmonEventPS represents a Sysmon event from PowerShell
type SysmonEventPS struct {
	RecordId      uint32 `json:"RecordId"`
	Id            uint32 `json:"Id"`
	TimeCreated   string `json:"TimeCreated"`
	Message       string `json:"Message"`
	ProviderName  string `json:"ProviderName"`
	ProcessId     uint32 `json:"ProcessId"`
}

// ReadSysmonEventsPS reads Sysmon events using PowerShell Get-WinEvent (optimized for low system load)
func (s *Scanner) ReadSysmonEventsPS(afterTime time.Time, eventIDs []int) ([]SysmonEventPS, error) {
	// Build EventID filter
	eventIDStrs := make([]string, len(eventIDs))
	for i, id := range eventIDs {
		eventIDStrs[i] = strconv.Itoa(id)
	}
	eventIDFilter := strings.Join(eventIDStrs, ",")
	
	// Optimized PowerShell command - minimal data, fast execution
	psScript := fmt.Sprintf(`
		try {
			$events = Get-WinEvent -FilterHashtable @{
				LogName='Microsoft-Windows-Sysmon/Operational'; 
				ID=%s; 
				StartTime=[DateTime]::Parse('%s')
			} -MaxEvents 20 -ErrorAction SilentlyContinue |
			Select-Object -First 5 RecordId, Id, @{N='TimeCreated';E={$_.TimeCreated.ToString('yyyy-MM-ddTHH:mm:ssZ')}}, @{N='Message';E={$_.Message}}
			
			if ($events) { $events | ConvertTo-Json -Compress -Depth 1 } else { "[]" }
		} catch { "[]" }
	`, eventIDFilter, afterTime.Format("2006-01-02T15:04:05"))
	
	// Only log script in debug mode to reduce noise
	// log.Printf("DEBUG: PowerShell script: %s", psScript)
	
	// Execute PowerShell command with shorter timeout for better performance
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	
	cmd := exec.CommandContext(ctx, "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", psScript)
	output, err := cmd.CombinedOutput()
	if err != nil {
		if ctx.Err() == context.DeadlineExceeded {
			log.Printf("DEBUG: PowerShell command timed out after 10 seconds")
			return nil, fmt.Errorf("PowerShell command timed out")
		}
		log.Printf("DEBUG: PowerShell error: %v", err)
		return nil, fmt.Errorf("PowerShell command failed: %v", err)
	}
	
	if len(output) == 0 {
		return []SysmonEventPS{}, nil
	}
	
	// Parse JSON output
	var events []SysmonEventPS
	
	// Handle both single event (object) and multiple events (array)
	outputStr := strings.TrimSpace(string(output))
	if strings.HasPrefix(outputStr, "[") {
		// Multiple events - array
		err = json.Unmarshal(output, &events)
	} else if strings.HasPrefix(outputStr, "{") {
		// Single event - object
		var singleEvent SysmonEventPS
		err = json.Unmarshal(output, &singleEvent)
		if err == nil {
			events = []SysmonEventPS{singleEvent}
		}
	}
	
	if err != nil {
		log.Printf("Failed to parse PowerShell JSON output: %v", err)
		return nil, fmt.Errorf("failed to parse PowerShell JSON output: %v", err)
	}
	return events, nil
}

// ProcessSysmonEventPS processes a Sysmon event from PowerShell
func (s *Scanner) ProcessSysmonEventPS(event *SysmonEventPS) {
	log.Printf("Processing Sysmon Event ID %d at %s", event.Id, event.TimeCreated)
	
	// Extract hash information from event message
	switch event.Id {
	case 15: // File create stream hash
		s.processSysmonFileHashEvent(event, "Hash=")
		
	case 29: // FileExecutableDetected  
		s.processSysmonFileHashEvent(event, "Hashes=")
	}
}

// processSysmonFileHashEvent extracts hash from event message and processes it
func (s *Scanner) processSysmonFileHashEvent(event *SysmonEventPS, hashPrefix string) {
	message := event.Message
	
	// Extract TargetFilename
	targetFilename := s.extractFieldFromMessage(message, "TargetFilename:")
	if targetFilename == "" {
		targetFilename = s.extractFieldFromMessage(message, "Image:")
	}
	
	// Extract hash information
	hashValue := s.extractFieldFromMessage(message, hashPrefix)
	
	if hashValue != "" && targetFilename != "" {
		log.Printf("Found hash in Event ID %d: %s -> %s", event.Id, targetFilename, hashValue)
		s.processHashesData(hashValue, targetFilename)
	} else {
		log.Printf("DEBUG: Could not extract hash or filename from Event ID %d", event.Id)
		log.Printf("DEBUG: Message excerpt: %s", message[:min(200, len(message))])
	}
}

// extractFieldFromMessage extracts a field value from Sysmon event message
func (s *Scanner) extractFieldFromMessage(message, fieldPrefix string) string {
	lines := strings.Split(message, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, fieldPrefix) {
			value := strings.TrimSpace(line[len(fieldPrefix):])
			return value
		}
	}
	return ""
}

// min returns the minimum of two integers
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// scanSysmonLogsPS scans Sysmon logs using PowerShell approach
func (s *Scanner) scanSysmonLogsPS() error {
	log.Printf("Starting Sysmon log scan using PowerShell Get-WinEvent")
	
	// Get events since last scan time - focus on Event ID 15, 29 only
	events, err := s.ReadSysmonEventsPS(s.lastScanTime, []int{15, 29})
	if err != nil {
		return fmt.Errorf("failed to read Sysmon events: %v", err)
	}
	
	log.Printf("Found %d Sysmon events since %v", len(events), s.lastScanTime)
	
	// Process each event
	eventsProcessed := 0
	for _, event := range events {
		// Parse the time string to compare with lastScanTime
		eventTime, err := time.Parse("2006-01-02T15:04:05Z", event.TimeCreated)
		if err != nil {
			log.Printf("DEBUG: Failed to parse event time %s: %v", event.TimeCreated, err)
			continue
		}
		
		if eventTime.After(s.lastScanTime) {
			s.ProcessSysmonEventPS(&event)
			eventsProcessed++
		}
	}
	
	log.Printf("PowerShell Sysmon scan completed, processed %d events", eventsProcessed)
	
	// Update last scan time
	s.lastScanTime = time.Now()
	log.Printf("Updated last scan time to %v for next scan", s.lastScanTime)
	
	return nil
} 