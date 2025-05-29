package blocker

import (
	"encoding/json"
	"fmt"
	"log"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"agent/config"
)

// Blocker handles blocking of malicious IPs and URLs
type Blocker struct {
	config      *config.Config
	blockedIPs  map[string]bool
	blockedURLs map[string]bool
	storagePath string
	
	// Performance optimization: batch save operations
	pendingSave bool
	saveTimer   *time.Timer
}

// BlockedItems represents the structure for persisting blocked items
type BlockedItems struct {
	BlockedIPs  map[string]bool `json:"blocked_ips"`
	BlockedURLs map[string]bool `json:"blocked_urls"`
}

// NewBlocker creates a new network blocker with configuration
func NewBlocker(cfg *config.Config, storagePath string) *Blocker {
	b := &Blocker{
		config:      cfg,
		blockedIPs:  make(map[string]bool),
		blockedURLs: make(map[string]bool),
		storagePath: storagePath,
	}
	
	// Load previously blocked items
	b.loadBlockedItems()
	
	return b
}

// loadBlockedItems loads the list of previously blocked IPs and URLs
func (b *Blocker) loadBlockedItems() {
	filePath := filepath.Join(b.storagePath, "blocked_items.json")
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		log.Printf("No existing blocked items file found at %s", filePath)
		return
	}

	data, err := os.ReadFile(filePath)
	if err != nil {
		log.Printf("Failed to read blocked items file: %v", err)
		return
	}

	var savedData BlockedItems
	if err := json.Unmarshal(data, &savedData); err != nil {
		log.Printf("Failed to unmarshal blocked items data: %v", err)
		return
	}

	if savedData.BlockedIPs != nil {
		b.blockedIPs = savedData.BlockedIPs
	}
	if savedData.BlockedURLs != nil {
		b.blockedURLs = savedData.BlockedURLs
	}

	log.Printf("Loaded blocked items: %d IPs, %d URLs", 
		len(b.blockedIPs), len(b.blockedURLs))
}

// saveBlockedItems saves the list of blocked IPs and URLs
func (b *Blocker) saveBlockedItems() {
	filePath := filepath.Join(b.storagePath, "blocked_items.json")
	
	data := BlockedItems{
		BlockedIPs:  b.blockedIPs,
		BlockedURLs: b.blockedURLs,
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
		len(b.blockedIPs), len(b.blockedURLs))
}

// saveBlockedItemsDelayed saves blocked items with a delay to batch operations
func (b *Blocker) saveBlockedItemsDelayed() {
	// If a save is already pending, reset the timer
	if b.pendingSave {
		if b.saveTimer != nil {
			b.saveTimer.Stop()
		}
	}
	
	b.pendingSave = true
	b.saveTimer = time.AfterFunc(2*time.Second, func() {
		b.saveBlockedItems()
		b.pendingSave = false
	})
}

// BlockIP blocks an IP address using Windows Firewall
func (b *Blocker) BlockIP(ip string) error {
	// Check if already blocked
	if b.blockedIPs[ip] {
		log.Printf("IP %s is already blocked", ip)
		return nil
	}
	
	log.Printf("Blocking IP address: %s", ip)
	
	// Block outbound traffic
	outCmd := exec.Command("netsh", "advfirewall", "firewall", "add", "rule",
		"name=EDR_Block_"+ip+"_Out",
		"dir=out",
		"action=block",
		"remoteip="+ip)
	
	if outOutput, err := outCmd.CombinedOutput(); err != nil {
		return fmt.Errorf("failed to block outbound IP %s: %v, output: %s", ip, err, string(outOutput))
	}

	// Block inbound traffic
	inCmd := exec.Command("netsh", "advfirewall", "firewall", "add", "rule",
		"name=EDR_Block_"+ip+"_In",
		"dir=in",
		"action=block",
		"remoteip="+ip)
	
	if inOutput, err := inCmd.CombinedOutput(); err != nil {
		// Try to clean up the outbound rule if inbound fails
		cleanupCmd := exec.Command("netsh", "advfirewall", "firewall", "delete", "rule", "name=EDR_Block_"+ip+"_Out")
		cleanupCmd.Run()
		return fmt.Errorf("failed to block inbound IP %s: %v, output: %s", ip, err, string(inOutput))
	}

	// Mark as blocked and persist
	b.blockedIPs[ip] = true
	b.saveBlockedItemsDelayed()
	
	log.Printf("Successfully blocked IP %s (inbound and outbound)", ip)
	return nil
}

// BlockURL blocks a URL by adding it to the hosts file
func (b *Blocker) BlockURL(url string) error {
	// Check if already blocked
	if b.blockedURLs[url] {
		log.Printf("URL %s is already blocked", url)
		return nil
	}
	
	log.Printf("Blocking URL: %s", url)
	
	// Extract domain from URL
	domain := b.extractDomain(url)
	if domain == "" {
		return fmt.Errorf("failed to extract domain from URL: %s", url)
	}
	
	// Try to block by modifying hosts file
	blocked, err := b.addDomainToHostsFile(domain)
	if err != nil {
		return err
	}
	
	// Mark as blocked and persist
	b.blockedURLs[url] = true
	b.saveBlockedItemsDelayed()
	
	if blocked {
		log.Printf("Successfully blocked URL %s by adding domain %s to hosts file", url, domain)
	} else {
		log.Printf("URL %s already blocked - domain %s exists in hosts file", url, domain)
	}
	
	return nil
}

// extractDomain extracts the domain from a URL
func (b *Blocker) extractDomain(urlStr string) string {
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

// addDomainToHostsFile adds a domain to the hosts file, pointing to the configured redirect IP
// Returns true if domain was added, false if it was already there
func (b *Blocker) addDomainToHostsFile(domain string) (bool, error) {
	hostsPath := b.config.HostsFilePath
	
	// Read current hosts file
	content, err := os.ReadFile(hostsPath)
	if err != nil {
		return false, fmt.Errorf("failed to read hosts file: %v", err)
	}
	
	// Check if domain is already in hosts file
	lines := strings.Split(string(content), "\n")
	blockLine := fmt.Sprintf("%s %s", b.config.BlockedIPRedirect, domain)
	
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

// IsIPBlocked checks if an IP is already blocked
func (b *Blocker) IsIPBlocked(ip string) bool {
	return b.blockedIPs[ip]
}

// IsURLBlocked checks if a URL is already blocked
func (b *Blocker) IsURLBlocked(url string) bool {
	return b.blockedURLs[url]
}

// GetBlockedIPs returns a copy of blocked IPs
func (b *Blocker) GetBlockedIPs() map[string]bool {
	result := make(map[string]bool)
	for ip, blocked := range b.blockedIPs {
		result[ip] = blocked
	}
	return result
}

// GetBlockedURLs returns a copy of blocked URLs
func (b *Blocker) GetBlockedURLs() map[string]bool {
	result := make(map[string]bool)
	for url, blocked := range b.blockedURLs {
		result[url] = blocked
	}
	return result
}

// GetBlockedCount returns the count of blocked IPs and URLs
func (b *Blocker) GetBlockedCount() (int, int) {
	return len(b.blockedIPs), len(b.blockedURLs)
} 