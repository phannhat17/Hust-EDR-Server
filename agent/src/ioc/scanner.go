package ioc

import (
	"context"
	"crypto/md5"
	"crypto/sha1"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
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
}

// NetworkBlocker handles blocking of malicious IPs and URLs
type NetworkBlocker struct {
	blockedIPs  map[string]bool
	blockedURLs map[string]bool
}

// NewNetworkBlocker creates a new network blocker
func NewNetworkBlocker() *NetworkBlocker {
	return &NetworkBlocker{
		blockedIPs:  make(map[string]bool),
		blockedURLs: make(map[string]bool),
	}
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
		networkBlocker:  NewNetworkBlocker(),
		sysmonLogPath:   sysmonLogPath,
	}
}

// Start starts the scanner
func (s *Scanner) Start() {
	log.Printf("Starting IOC scanner with interval %d minutes", s.intervalMinutes)
	
	// Initialize IP blockers on startup to ensure protection after restart
	s.initializeIPBlocking()
	
	// Run initial scan
	go s.runScan()
	
	// Start periodic scans
	go func() {
		ticker := time.NewTicker(time.Duration(s.intervalMinutes) * time.Minute)
		defer ticker.Stop()
		
		for {
			select {
			case <-ticker.C:
				go s.runScan()
			case <-s.ctx.Done():
				log.Printf("IOC scanner stopped")
				return
			}
		}
	}()
}

// Stop stops the scanner
func (s *Scanner) Stop() {
	s.cancel()
}

// initializeIPBlocking initializes blocking of all malicious IPs immediately on startup
func (s *Scanner) initializeIPBlocking() {
	log.Printf("Initializing IP blocking for all IOC IPs")
	
	s.manager.mu.RLock()
	for ip := range s.manager.IPAddresses {
		s.blockIP(ip)
	}
	s.manager.mu.RUnlock()
	
	log.Printf("IP blocking initialized for %d IPs", len(s.networkBlocker.blockedIPs))
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
		s.networkBlocker.blockedIPs[ip] = true
		
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

// runScan performs a complete scan
func (s *Scanner) runScan() {
	log.Printf("Starting IOC scan")
	start := time.Now()
	
	// Check for new IPs to block
	s.checkAndBlockNewIPs()
	
	// Scan sysmon logs for file hash matches
	s.scanSysmonLogs()
	
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

// scanSysmonLogs scans Windows sysmon logs for file creation events and checks hashes
func (s *Scanner) scanSysmonLogs() {
	log.Printf("Scanning Windows sysmon logs for file hash matches")
	s.scanWindowsSysmonLogs()
}

// scanWindowsSysmonLogs scans Windows Sysmon event logs for file creation events
func (s *Scanner) scanWindowsSysmonLogs() {
	// On Windows, we need to export recent events to a temporary file
	tempFile := filepath.Join(os.TempDir(), "edr_sysmon_export.xml")
	
	// Export events from last 24 hours (adjust timeframe as needed)
	cmd := exec.Command("wevtutil", "qe", "Microsoft-Windows-Sysmon/Operational", 
		"/q:*[System[(EventID=1 or EventID=11) and TimeCreated[timediff(@SystemTime) <= 86400000]]]",
		"/e:Events", "/f:xml", "/uni:true")
	output, err := cmd.Output()
	if err != nil {
		log.Printf("Failed to export sysmon events: %v", err)
		return
	}
	
	// Write to temp file
	if err := os.WriteFile(tempFile, output, 0644); err != nil {
		log.Printf("Failed to write sysmon events to temp file: %v", err)
		return
	}
	defer os.Remove(tempFile)
	
	// Parse the XML for file hash information
	fileContent, err := os.ReadFile(tempFile)
	if err != nil {
		log.Printf("Failed to read sysmon export: %v", err)
		return
	}
	
	// Simple regex to find hashes and file paths
	hashRegex := regexp.MustCompile(`<Data Name="Hash">([^<]+)</Data>`)
	pathRegex := regexp.MustCompile(`<Data Name="TargetFilename">([^<]+)</Data>`)
	
	hashMatches := hashRegex.FindAllStringSubmatch(string(fileContent), -1)
	pathMatches := pathRegex.FindAllStringSubmatch(string(fileContent), -1)
	
	if len(hashMatches) != len(pathMatches) {
		log.Printf("Mismatch between hash and path count in sysmon logs")
		return
	}
	
	for i := 0; i < len(hashMatches); i++ {
		if i < len(pathMatches) {
			hashData := hashMatches[i][1]
			filePath := pathMatches[i][1]
			
			// Hash data might contain multiple hash algorithms
			hashes := strings.Split(hashData, ",")
			
			for _, hash := range hashes {
				parts := strings.SplitN(hash, "=", 2)
				if len(parts) == 2 {
					hashValue := strings.TrimSpace(parts[1])
					
					// Check if hash matches IOCs
					match, ioc := s.manager.CheckFileHash(hashValue)
					if match {
						log.Printf("Found file hash IOC match: %s (%s)", filePath, hashValue)
						
						// Delete the malicious file
						if err := os.Remove(filePath); err != nil {
							log.Printf("Failed to delete malicious file %s: %v", filePath, err)
						} else {
							log.Printf("Successfully deleted malicious file: %s", filePath)
						}
						
						// Report the match
						if s.reportCallback != nil {
							s.reportCallback(
								s.ctx,
								pb.IOCType_IOC_HASH,
								ioc.Value,
								hashValue,
								fmt.Sprintf("Malicious file: %s (deleted: %v)", filePath, err == nil),
								ioc.Severity,
							)
						}
					}
				}
			}
		}
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