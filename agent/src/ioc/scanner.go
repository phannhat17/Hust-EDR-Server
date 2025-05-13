package ioc

import (
	"context"
	"crypto/md5"
	"crypto/sha1"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"io"
	"log"
	"net"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	pb "agent/proto"
)

// Scanner scans the system for IOCs
type Scanner struct {
	manager         *Manager
	reportCallback  func(context.Context, pb.IOCType, string, string, string, string) error
	intervalMinutes int
	ctx             context.Context
	cancel          context.CancelFunc
	networkBlocker  *NetworkBlocker
	sysmonLogPath   string
	triggerScan     chan struct{}
	lastScanTime    time.Time // Track when the last scan was performed
}

// NetworkBlocker handles blocking of malicious IPs and URLs
type NetworkBlocker struct {
	blockedIPs  map[string]bool
	blockedURLs map[string]bool
	storagePath string
}

// NewNetworkBlocker creates a new network blocker
func NewNetworkBlocker(storagePath string) *NetworkBlocker {
	nb := &NetworkBlocker{
		blockedIPs:  make(map[string]bool),
		blockedURLs: make(map[string]bool),
		storagePath: storagePath,
	}
	
	// Load previously blocked items
	nb.LoadBlockedItems()
	
	return nb
}

// LoadBlockedItems loads the list of previously blocked IPs and URLs
func (nb *NetworkBlocker) LoadBlockedItems() {
	filePath := filepath.Join(nb.storagePath, "blocked_items.json")
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		log.Printf("No existing blocked items file found at %s", filePath)
		return
	}

	data, err := os.ReadFile(filePath)
	if err != nil {
		log.Printf("Failed to read blocked items file: %v", err)
		return
	}

	var savedData struct {
		BlockedIPs  map[string]bool `json:"blocked_ips"`
		BlockedURLs map[string]bool `json:"blocked_urls"`
	}

	if err := json.Unmarshal(data, &savedData); err != nil {
		log.Printf("Failed to unmarshal blocked items data: %v", err)
		return
	}

	nb.blockedIPs = savedData.BlockedIPs
	nb.blockedURLs = savedData.BlockedURLs

	log.Printf("Loaded blocked items: %d IPs, %d URLs", 
		len(nb.blockedIPs), len(nb.blockedURLs))
}

// SaveBlockedItems saves the list of blocked IPs and URLs
func (nb *NetworkBlocker) SaveBlockedItems() {
	filePath := filepath.Join(nb.storagePath, "blocked_items.json")
	
	data := struct {
		BlockedIPs  map[string]bool `json:"blocked_ips"`
		BlockedURLs map[string]bool `json:"blocked_urls"`
	}{
		BlockedIPs:  nb.blockedIPs,
		BlockedURLs: nb.blockedURLs,
	}
	
	jsonData, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		log.Printf("Failed to marshal blocked items data: %v", err)
		return
	}

	if err := os.WriteFile(filePath, jsonData, 0644); err != nil {
		log.Printf("Failed to write blocked items file: %v", err)
		return
	}

	log.Printf("Saved blocked items: %d IPs, %d URLs", 
		len(nb.blockedIPs), len(nb.blockedURLs))
}

// MarkIPBlocked marks an IP as blocked and persists this information
func (nb *NetworkBlocker) MarkIPBlocked(ip string) {
	nb.blockedIPs[ip] = true
	nb.SaveBlockedItems()
}

// MarkURLBlocked marks a URL as blocked and persists this information
func (nb *NetworkBlocker) MarkURLBlocked(url string) {
	nb.blockedURLs[url] = true
	nb.SaveBlockedItems()
}

// NewScanner creates a new IOC scanner
func NewScanner(manager *Manager, reportCallback func(context.Context, pb.IOCType, string, string, string, string) error, intervalMinutes int) *Scanner {
	ctx, cancel := context.WithCancel(context.Background())
	
	// Windows sysmon log path
	sysmonLogPath := "C:\\Windows\\System32\\winevt\\Logs\\Microsoft-Windows-Sysmon%4Operational.evtx"
	
	return &Scanner{
		manager:         manager,
		reportCallback:  reportCallback,
		intervalMinutes: intervalMinutes,
		ctx:             ctx,
		cancel:          cancel,
		networkBlocker:  NewNetworkBlocker(manager.StoragePath),
		sysmonLogPath:   sysmonLogPath,
		triggerScan:     make(chan struct{}, 1),
		lastScanTime:    time.Now(), // Start with current time since we skip first scan
	}
}

// Start starts the scanner
func (s *Scanner) Start() {
	log.Printf("Starting IOC scanner with interval %d minutes", s.intervalMinutes)
	
	// Initialize IP blockers on startup to ensure protection after restart
	s.initializeIPBlocking()
	
	// Initialize URL blockers on startup
	s.initializeURLBlocking()
	
	// Flag to indicate this is first run
	isFirstRun := true
	
	// Run initial scan
	go s.runScan(isFirstRun)
	
	// Start periodic scans only if interval is positive
	go func() {
		// Use default interval of 5 minutes if intervalMinutes is non-positive
		interval := s.intervalMinutes
		if interval <= 0 {
			interval = 5
			log.Printf("WARNING: Scanner interval was %d minutes, defaulting to %d minutes", s.intervalMinutes, interval)
		}
		
		ticker := time.NewTicker(time.Duration(interval) * time.Minute)
		defer ticker.Stop()
		
		for {
			select {
			case <-ticker.C:
				go s.runScan(false) // Not first run
			case <-s.triggerScan:
				// Perform immediate scan
				log.Printf("Triggering immediate IOC scan")
				go s.runScan(false) // Not first run
				
				// Reset the timer
				ticker.Reset(time.Duration(interval) * time.Minute)
			case <-s.ctx.Done():
				log.Printf("IOC scanner stopped")
				return
			}
		}
	}()
}

// TriggerScan triggers an immediate scan and resets the timer
func (s *Scanner) TriggerScan() {
	// Use non-blocking send to avoid hanging if channel is full
	select {
	case s.triggerScan <- struct{}{}:
		log.Printf("IOC scan triggered")
	default:
		log.Printf("Scan already triggered, waiting for completion")
	}
}

// Stop stops the scanner
func (s *Scanner) Stop() {
	s.cancel()
}

// initializeIPBlocking initializes blocking of all malicious IPs immediately on startup
func (s *Scanner) initializeIPBlocking() {
	log.Printf("Initializing IP blocking for all IOC IPs")
	
	// Count new blocks only
	newBlocks := 0
	
	s.manager.mu.RLock()
	for ip := range s.manager.IPAddresses {
		if !s.networkBlocker.blockedIPs[ip] {
			s.blockIP(ip)
			newBlocks++
		} else {
			log.Printf("Skipping already blocked IP: %s", ip)
		}
	}
	s.manager.mu.RUnlock()
	
	log.Printf("IP blocking initialized: %d new blocks, %d total blocked IPs", 
		newBlocks, len(s.networkBlocker.blockedIPs))
}

// initializeURLBlocking initializes blocking of all malicious URLs immediately on startup
func (s *Scanner) initializeURLBlocking() {
	log.Printf("Initializing URL blocking for all IOC URLs")
	
	// Count new blocks only
	newBlocks := 0
	
	s.manager.mu.RLock()
	for url := range s.manager.URLs {
		if !s.networkBlocker.blockedURLs[url] {
			s.blockURL(url)
			newBlocks++
		} else {
			log.Printf("Skipping already blocked URL: %s", url)
		}
	}
	s.manager.mu.RUnlock()
	
	log.Printf("URL blocking initialized: %d new blocks, %d total blocked URLs", 
		newBlocks, len(s.networkBlocker.blockedURLs))
}

// blockIP blocks an IP immediately using Windows Firewall
func (s *Scanner) blockIP(ip string) {
	// Check if already blocked
	if s.networkBlocker.blockedIPs[ip] {
		return
	}
	
	var err error
	var message string
	
	// Windows firewall - outbound rule
	cmd := exec.Command("netsh", "advfirewall", "firewall", "add", "rule",
		"name=BlockEDR_"+ip,
		"dir=out",
		"action=block",
		"remoteip="+ip)
	_, err = cmd.Output()
	
	// Add inbound rule too
	if err == nil {
		cmd = exec.Command("netsh", "advfirewall", "firewall", "add", "rule",
			"name=BlockEDR_In_"+ip,
			"dir=in",
			"action=block",
			"remoteip="+ip)
		_, err = cmd.Output()
	}
	
	if err != nil {
		message = fmt.Sprintf("Failed to block IP %s: %v", ip, err)
		log.Printf(message)
	} else {
		message = fmt.Sprintf("Successfully blocked IP %s", ip)
		log.Printf(message)
		s.networkBlocker.MarkIPBlocked(ip)
		
		// Report the action
		if s.reportCallback != nil {
			ioc, exists := s.manager.IPAddresses[ip]
			if exists {
				s.reportCallback(
					s.ctx,
					pb.IOCType_IOC_IP,
					ip,
					ip,
					"IP automatically blocked on startup/update",
					ioc.Severity,
				)
			}
		}
	}
}

// blockURL blocks a URL by adding it to the hosts file pointing to 127.0.0.1
func (s *Scanner) blockURL(url string) {
	// Check if already blocked
	if s.networkBlocker.blockedURLs[url] {
		return
	}
	
	// Extract domain from URL
	domain := extractDomain(url)
	if domain == "" {
		log.Printf("Failed to extract domain from URL: %s", url)
		return
	}
	
	// Windows hosts file path
	hostsPath := "C:\\Windows\\System32\\drivers\\etc\\hosts"
	
	// Try to block by modifying hosts file
	blocked, err := addDomainToHostsFile(hostsPath, domain)
	
	if err != nil {
		log.Printf("Failed to block URL %s: %v", url, err)
	} else if blocked {
		log.Printf("Successfully blocked URL %s by adding domain %s to hosts file", url, domain)
		s.networkBlocker.MarkURLBlocked(url)
		
		// Report the action
		if s.reportCallback != nil {
			ioc, exists := s.manager.URLs[url]
			if exists {
				s.reportCallback(
					s.ctx,
					pb.IOCType_IOC_URL,
					url,
					url,
					fmt.Sprintf("URL blocked by adding domain %s to hosts file", domain),
					ioc.Severity,
				)
			}
		}
	} else {
		log.Printf("Domain %s already exists in hosts file", domain)
		s.networkBlocker.MarkURLBlocked(url)
	}
}

// extractDomain extracts the domain from a URL
func extractDomain(urlStr string) string {
	// Add http:// prefix if not present (needed for url.Parse)
	if !strings.HasPrefix(urlStr, "http://") && !strings.HasPrefix(urlStr, "https://") {
		urlStr = "http://" + urlStr
	}
	
	// Parse the URL
	parsedURL, err := url.Parse(urlStr)
	if err != nil {
		log.Printf("Failed to parse URL %s: %v", urlStr, err)
		return ""
	}
	
	// Return just the host part (domain)
	return parsedURL.Host
}

// addDomainToHostsFile adds a domain to the hosts file, pointing to 127.0.0.1
// Returns true if domain was added, false if it was already there
func addDomainToHostsFile(hostsPath string, domain string) (bool, error) {
	// Read current hosts file
	content, err := os.ReadFile(hostsPath)
	if err != nil {
		return false, fmt.Errorf("failed to read hosts file: %v", err)
	}
	
	// Check if domain is already in hosts file
	lines := strings.Split(string(content), "\n")
	blockLine := fmt.Sprintf("127.0.0.1 %s", domain)
	
	for _, line := range lines {
		trimmedLine := strings.TrimSpace(line)
		if trimmedLine == blockLine || strings.HasSuffix(trimmedLine, " "+domain) {
			// Domain already blocked
			return false, nil
		}
	}
	
	// Add domain to hosts file
	file, err := os.OpenFile(hostsPath, os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return false, fmt.Errorf("failed to open hosts file for writing: %v", err)
	}
	defer file.Close()
	
	// Add newline if file doesn't end with one
	if !strings.HasSuffix(string(content), "\n") {
		if _, err := file.WriteString("\n"); err != nil {
			return false, fmt.Errorf("failed to write newline to hosts file: %v", err)
		}
	}
	
	// Add block entry
	if _, err := file.WriteString(blockLine + "\n"); err != nil {
		return false, fmt.Errorf("failed to write to hosts file: %v", err)
	}
	
	return true, nil
}

// checkAndBlockNewURLs checks for any new URLs in the IOC database that need blocking
func (s *Scanner) checkAndBlockNewURLs() {
	log.Printf("Checking for new malicious URLs to block")
	
	s.manager.mu.RLock()
	for url, ioc := range s.manager.URLs {
		// If not already blocked, block it now
		if !s.networkBlocker.blockedURLs[url] {
			log.Printf("Found new malicious URL to block: %s (severity: %s)", url, ioc.Severity)
			s.blockURL(url)
		}
	}
	s.manager.mu.RUnlock()
}

// runScan performs a complete scan
func (s *Scanner) runScan(isFirstRun bool) {
	log.Printf("Starting IOC scan")
	start := time.Now()
	
	// Check for new IPs to block
	s.checkAndBlockNewIPs()
	
	// Check for new URLs to block
	s.checkAndBlockNewURLs()
	
	// Skip file hash scanning on first run to improve startup performance
	if isFirstRun {
		log.Printf("Skipping file hash scanning on first run for better performance")
	} else {
		// Scan sysmon logs for file hash matches
		s.scanSysmonLogs()
	}
	
	duration := time.Since(start)
	log.Printf("IOC scan completed in %v", duration)
}

// checkAndBlockNewIPs checks for any new IPs in the IOC database that need blocking
func (s *Scanner) checkAndBlockNewIPs() {
	log.Printf("Checking for new malicious IPs to block")
	
	s.manager.mu.RLock()
	for ip, ioc := range s.manager.IPAddresses {
		// If not already blocked, block it now
		if !s.networkBlocker.blockedIPs[ip] {
			log.Printf("Found new malicious IP to block: %s (severity: %s)", ip, ioc.Severity)
			s.blockIP(ip)
		}
	}
	s.manager.mu.RUnlock()
}

// scanSysmonLogs scans Windows sysmon logs for file hash matches
func (s *Scanner) scanSysmonLogs() {
	log.Printf("Scanning Windows sysmon logs for file hash matches")
	s.scanWindowsSysmonLogs()
}

// XML structures for parsing Sysmon events
type Events struct {
	XMLName xml.Name `xml:"Events"`
	Event   []Event  `xml:"Event"`
}

type Event struct {
	System    System    `xml:"System"`
	EventData EventData `xml:"EventData"`
}

type System struct {
	EventID    int       `xml:"EventID"`
	TimeCreated TimeCreated `xml:"TimeCreated"`
}

type TimeCreated struct {
	SystemTime string `xml:"SystemTime,attr"`
}

type EventData struct {
	Data []Data `xml:"Data"`
}

type Data struct {
	Name  string `xml:"Name,attr"`
	Value string `xml:",chardata"`
}

// scanWindowsSysmonLogs scans Windows Sysmon event logs for file creation events
func (s *Scanner) scanWindowsSysmonLogs() {
	// Get the timestamp for last scan in the format expected by wevtutil
	// Format: yyyy-MM-ddTHH:mm:ss.sssZ
	lastScanTimeStr := s.lastScanTime.Format("2006-01-02T15:04:05.000Z")
	
	// On Windows, we need to export recent events to a temporary file
	tempFile := filepath.Join(os.TempDir(), "edr_sysmon_export.xml")
	
	// Build query to get events since last scan (both file creation and hash events)
	// EventID 1 = Process creation
	// EventID 11 = File creation
	// EventID 15 = File create stream hash
	// EventID 23 = File delete
	// EventID 29 = Remote thread creation - often used in malware injection
	queryStr := fmt.Sprintf("*[System[(EventID=1 or EventID=11 or EventID=15 or EventID=23 or EventID=29) and TimeCreated[@SystemTime>'%s']]]", lastScanTimeStr)
	
	// Export sysmon events
	var output []byte
	var err error
	
	// Try up to 3 times with increasing delays
	for attempt := 1; attempt <= 3; attempt++ {
		cmd := exec.Command("wevtutil", "qe", "Microsoft-Windows-Sysmon/Operational", 
			"/q:"+queryStr, "/e:Events", "/f:xml", "/uni:true")
		
		output, err = cmd.Output()
		if err == nil {
			break
		}
		
		log.Printf("Attempt %d: Failed to export sysmon events: %v", attempt, err)
		if attempt < 3 {
			// Wait with exponential backoff
			waitTime := time.Duration(attempt*attempt) * time.Second
			log.Printf("Retrying in %v...", waitTime)
			time.Sleep(waitTime)
		}
	}
	
	if err != nil {
		log.Printf("All attempts to export sysmon events failed. Last error: %v", err)
		return
	}
	
	// Write to temp file
	if err := os.WriteFile(tempFile, output, 0644); err != nil {
		log.Printf("Failed to write sysmon events to temp file: %v", err)
		return
	}
	defer os.Remove(tempFile)
	
	// Record current time for next scan
	s.lastScanTime = time.Now()
	
	// Parse the XML properly
	fileContent, err := os.ReadFile(tempFile)
	if err != nil {
		log.Printf("Failed to read sysmon export: %v", err)
		return
	}
	
	var events Events
	if err := xml.Unmarshal(fileContent, &events); err != nil {
		log.Printf("Failed to parse sysmon XML: %v", err)
		return
	}
	
	// Process each event
	for _, event := range events.Event {
		// Map to store data for each event
		eventData := make(map[string]string)
		
		// Extract data
		for _, data := range event.EventData.Data {
			if data.Name != "" {
				eventData[data.Name] = data.Value
			}
		}
		
		// Process based on event type
		switch event.System.EventID {
		case 1: // Process creation
			if hash, ok := eventData["Hashes"]; ok {
				image := eventData["Image"]
				s.processHashesData(hash, image)
			}
		case 11: // File creation
			targetPath := eventData["TargetFilename"]
			// For file creation, try to calculate hash ourselves
			if targetPath != "" {
				hashValue, err := s.calculateFileHash(targetPath)
				if err == nil {
					// Check if hash matches IOCs
					match, ioc := s.manager.CheckFileHash(hashValue)
					if match {
						s.handleMaliciousFile(targetPath, hashValue, &ioc)
					}
				}
			}
		case 15: // File create stream hash
			if hash, ok := eventData["Hash"]; ok {
				filePath := eventData["TargetFilename"]
				s.processHashesData(hash, filePath)
			}
		case 23: // File delete (still check in case a malicious file was deleted)
			if hash, ok := eventData["Hashes"]; ok {
				image := eventData["Image"]
				s.processHashesData(hash, image)
			}
		case 29: // Remote thread creation (potential code injection)
			sourceImage := eventData["SourceImage"]
			targetImage := eventData["TargetImage"]
			
			// Get file hashes for both processes if possible
			sourceHash, err := s.calculateFileHash(sourceImage)
			if err == nil {
				// Check source process hash
				match, ioc := s.manager.CheckFileHash(sourceHash)
				if match {
					log.Printf("Malicious process creating remote thread detected: %s (%s)", sourceImage, sourceHash)
					s.handleMaliciousFile(sourceImage, sourceHash, &ioc)
				}
			}
			
			// Check target process too (in case malware is injecting into a known bad process)
			targetHash, err := s.calculateFileHash(targetImage)
			if err == nil {
				match, ioc := s.manager.CheckFileHash(targetHash)
				if match {
					log.Printf("Remote thread created in malicious process: %s (%s)", targetImage, targetHash)
					s.handleMaliciousFile(targetImage, targetHash, &ioc)
				}
			}
			
			// Log the event for auditing purposes even if no matches
			log.Printf("Remote thread created from %s to %s", sourceImage, targetImage)
		}
	}
	
	log.Printf("Sysmon log scan complete, found %d events", len(events.Event))
}

// processHashesData processes hash data in format SHA256=X,MD5=Y,SHA1=Z
func (s *Scanner) processHashesData(hashData string, filePath string) {
	// Hash data might contain multiple hash algorithms
	hashes := strings.Split(hashData, ",")
	
	for _, hash := range hashes {
		parts := strings.SplitN(hash, "=", 2)
		if len(parts) == 2 {
			hashValue := strings.TrimSpace(parts[1])
			
			// Check if hash matches IOCs
			match, ioc := s.manager.CheckFileHash(hashValue)
			if match {
				s.handleMaliciousFile(filePath, hashValue, &ioc)
			}
		}
	}
}

// handleMaliciousFile takes action on a malicious file
func (s *Scanner) handleMaliciousFile(filePath string, hashValue string, ioc *IOC) {
	log.Printf("Found file hash IOC match: %s (%s)", filePath, hashValue)
	
	fileDeleted := false
	
	// Delete the malicious file
	if err := os.Remove(filePath); err != nil {
		log.Printf("Failed to delete malicious file %s: %v", filePath, err)
	} else {
		log.Printf("Successfully deleted malicious file: %s", filePath)
		fileDeleted = true
	}
	
	// Report the match
	if s.reportCallback != nil {
		s.reportCallback(
			s.ctx,
			pb.IOCType_IOC_HASH,
			ioc.Value,
			hashValue,
			fmt.Sprintf("Malicious file: %s (deleted: %v)", filePath, fileDeleted),
			ioc.Severity,
		)
	}
}

// calculateFileHash calculates SHA256 hash of a file
func (s *Scanner) calculateFileHash(filePath string) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()
	
	// Calculate multiple hash types
	md5Hash := md5.New()
	sha1Hash := sha1.New()
	sha256Hash := sha256.New()
	
	multiWriter := io.MultiWriter(md5Hash, sha1Hash, sha256Hash)
	
	if _, err := io.Copy(multiWriter, file); err != nil {
		return "", err
	}
	
	// Return SHA256 hash by default
	return hex.EncodeToString(sha256Hash.Sum(nil)), nil
}

// GetMD5 calculates MD5 hash of a file
func GetMD5(filePath string) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()
	
	hash := md5.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}
	
	return hex.EncodeToString(hash.Sum(nil)), nil
}

// GetSHA1 calculates SHA1 hash of a file
func GetSHA1(filePath string) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()
	
	hash := sha1.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}
	
	return hex.EncodeToString(hash.Sum(nil)), nil
}

// GetSHA256 calculates SHA256 hash of a file
func GetSHA256(filePath string) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()
	
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}
	
	return hex.EncodeToString(hash.Sum(nil)), nil
}

// GetLocalIP returns the non-loopback local IP of the host
func GetLocalIP() string {
	addrs, err := net.InterfaceAddrs()
	if err != nil {
		return ""
	}
	for _, address := range addrs {
		// Check the address type and make sure it's not a loopback
		if ipnet, ok := address.(*net.IPNet); ok && !ipnet.IP.IsLoopback() {
			if ipnet.IP.To4() != nil {
				return ipnet.IP.String()
			}
		}
	}
	return ""
} 