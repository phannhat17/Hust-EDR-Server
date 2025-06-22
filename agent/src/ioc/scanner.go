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
	"strings"
	"time"

	pb "agent/proto"
	"agent/config"
	"agent/blocker"
)

// Scanner scans the system for IOCs
type Scanner struct {
	manager         *Manager
	reportCallback  func(context.Context, pb.IOCType, string, string, string, string) error
	intervalMinutes int
	ctx             context.Context
	cancel          context.CancelFunc
	blocker         *blocker.Blocker
	config          *config.Config
	triggerScan     chan struct{}
	lastScanTime    time.Time // Track when the last scan was performed
}



// NewScanner creates a new IOC scanner (legacy function)
func NewScanner(manager *Manager, reportCallback func(context.Context, pb.IOCType, string, string, string, string) error, intervalMinutes int) *Scanner {
	// Create a default config for legacy compatibility
	cfg := config.NewDefaultConfig()
	cfg.ScanInterval = intervalMinutes
	
	return NewScannerWithConfig(manager, reportCallback, cfg)
}

// NewScannerWithConfig creates a new IOC scanner with configuration
func NewScannerWithConfig(manager *Manager, reportCallback func(context.Context, pb.IOCType, string, string, string, string) error, cfg *config.Config) *Scanner {
	ctx, cancel := context.WithCancel(context.Background())
	
	return &Scanner{
		manager:         manager,
		reportCallback:  reportCallback,
		intervalMinutes: cfg.ScanInterval,
		ctx:             ctx,
		cancel:          cancel,
		blocker:         blocker.NewBlocker(cfg, manager.StoragePath),
		config:          cfg,
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
		// Use default interval of 10 minutes if intervalMinutes is non-positive (optimized for low system load)
		interval := s.intervalMinutes
		if interval <= 0 {
			interval = 10
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
		if !s.blocker.IsIPBlocked(ip) {
			s.blockIP(ip)
			newBlocks++
		} else {
			log.Printf("Skipping already blocked IP: %s", ip)
		}
	}
	s.manager.mu.RUnlock()
	
	ipCount, _ := s.blocker.GetBlockedCount()
	log.Printf("IP blocking initialized: %d new blocks, %d total blocked IPs", 
		newBlocks, ipCount)
}

// initializeURLBlocking initializes blocking of all malicious URLs immediately on startup
func (s *Scanner) initializeURLBlocking() {
	log.Printf("Initializing URL blocking for all IOC URLs")
	
	// Count new blocks only
	newBlocks := 0
	
	s.manager.mu.RLock()
	for url := range s.manager.URLs {
		if !s.blocker.IsURLBlocked(url) {
			s.blockURL(url)
			newBlocks++
		} else {
			log.Printf("Skipping already blocked URL: %s", url)
		}
	}
	s.manager.mu.RUnlock()
	
	_, urlCount := s.blocker.GetBlockedCount()
	log.Printf("URL blocking initialized: %d new blocks, %d total blocked URLs", 
		newBlocks, urlCount)
}

// blockIP blocks an IP immediately using Windows Firewall
func (s *Scanner) blockIP(ip string) {
	// Use the centralized blocker
	err := s.blocker.BlockIP(ip)
	
	if err != nil {
		log.Printf("Failed to block IP %s: %v", ip, err)
	} else {
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

// blockURL blocks a URL by adding it to the hosts file
func (s *Scanner) blockURL(url string) {
	// Use the centralized blocker
	err := s.blocker.BlockURL(url)
	
	if err != nil {
		log.Printf("Failed to block URL %s: %v", url, err)
	} else {
		// Report the action
		if s.reportCallback != nil {
			ioc, exists := s.manager.URLs[url]
			if exists {
				s.reportCallback(
					s.ctx,
					pb.IOCType_IOC_URL,
					url,
					url,
					"URL blocked by adding domain to hosts file",
					ioc.Severity,
				)
			}
		}
	}
}

// checkAndBlockNewURLs checks for any new URLs in the IOC database that need blocking
func (s *Scanner) checkAndBlockNewURLs() {
	log.Printf("Checking for new malicious URLs to block")
	
	s.manager.mu.RLock()
	for url, ioc := range s.manager.URLs {
		// If not already blocked, block it now
		if !s.blocker.IsURLBlocked(url) {
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
		if !s.blocker.IsIPBlocked(ip) {
			log.Printf("Found new malicious IP to block: %s (severity: %s)", ip, ioc.Severity)
			s.blockIP(ip)
		}
	}
	s.manager.mu.RUnlock()
}

// scanSysmonLogs scans Windows sysmon logs for file hash matches
func (s *Scanner) scanSysmonLogs() {
	log.Printf("Scanning Windows sysmon logs for file hash matches")
	
	// Use PowerShell approach only (Windows Event Log API doesn't work reliably with Sysmon logs)
	if err := s.scanSysmonLogsPS(); err != nil {
		log.Printf("PowerShell scanning failed: %v", err)
		log.Printf("Unable to scan Sysmon logs - PowerShell Get-WinEvent is the only reliable method for Sysmon log access")
	}
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