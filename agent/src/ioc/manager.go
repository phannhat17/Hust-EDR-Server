package ioc

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

// IOCType represents the type of IOC
type IOCType int

const (
	TypeIP IOCType = iota
	TypeFileHash
	TypeURL
)

// IOC represents an indicator of compromise
type IOC struct {
	Value       string            `json:"value"`
	Type        IOCType           `json:"type"`
	Description string            `json:"description"`
	Severity    string            `json:"severity"`
	Metadata    map[string]string `json:"metadata,omitempty"`
}

// Manager manages IOCs locally on the agent
type Manager struct {
	IPAddresses  map[string]IOC `json:"ip_addresses"`
	FileHashes   map[string]IOC `json:"file_hashes"`
	URLs         map[string]IOC `json:"urls"`
	Version      int64          `json:"version"`
	StoragePath  string         `json:"-"`
	mu           sync.RWMutex   `json:"-"`
}

// NewManager creates a new IOC manager
func NewManager(storagePath string) *Manager {
	// Create storage directory if it doesn't exist
	if err := os.MkdirAll(storagePath, 0755); err != nil {
		log.Printf("WARNING: Failed to create IOC storage directory: %v", err)
	}

	manager := &Manager{
		IPAddresses:  make(map[string]IOC),
		FileHashes:   make(map[string]IOC),
		URLs:         make(map[string]IOC),
		Version:      0,
		StoragePath:  storagePath,
	}

	// Load existing IOCs from file
	manager.LoadFromFile()

	return manager
}

// LoadFromFile loads IOCs from a JSON file
func (m *Manager) LoadFromFile() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	filePath := filepath.Join(m.StoragePath, "iocs.json")
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		log.Printf("No existing IOC file found at %s, starting with empty database", filePath)
		return nil
	}

	data, err := os.ReadFile(filePath)
	if err != nil {
		return fmt.Errorf("failed to read IOC file: %v", err)
	}

	type savedData struct {
		IPAddresses  map[string]IOC `json:"ip_addresses"`
		FileHashes   map[string]IOC `json:"file_hashes"`
		URLs         map[string]IOC `json:"urls"`
		Version      int64          `json:"version"`
	}

	var sd savedData
	if err := json.Unmarshal(data, &sd); err != nil {
		return fmt.Errorf("failed to unmarshal IOC data: %v", err)
	}

	m.IPAddresses = sd.IPAddresses
	m.FileHashes = sd.FileHashes
	m.URLs = sd.URLs
	m.Version = sd.Version

	log.Printf("Loaded IOCs from file: %d IPs, %d file hashes, %d URLs, version %d",
		len(m.IPAddresses), len(m.FileHashes), len(m.URLs), m.Version)

	return nil
}

// SaveToFile saves IOCs to a JSON file
func (m *Manager) SaveToFile() error {
	m.mu.RLock()
	defer m.mu.RUnlock()

	filePath := filepath.Join(m.StoragePath, "iocs.json")
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal IOC data: %v", err)
	}

	if err := os.WriteFile(filePath, data, 0644); err != nil {
		return fmt.Errorf("failed to write IOC file: %v", err)
	}

	log.Printf("Saved IOCs to file: %d IPs, %d file hashes, %d URLs, version %d",
		len(m.IPAddresses), len(m.FileHashes), len(m.URLs), m.Version)

	return nil
}

// AddIP adds an IP address IOC
func (m *Manager) AddIP(ip, description, severity string) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.IPAddresses[ip] = IOC{
		Value:       ip,
		Type:        TypeIP,
		Description: description,
		Severity:    severity,
	}
}

// AddFileHash adds a file hash IOC
func (m *Manager) AddFileHash(hash, hashType, description, severity string) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.FileHashes[strings.ToLower(hash)] = IOC{
		Value:       strings.ToLower(hash),
		Type:        TypeFileHash,
		Description: description,
		Severity:    severity,
		Metadata: map[string]string{
			"hash_type": hashType,
		},
	}
}

// AddURL adds a URL IOC
func (m *Manager) AddURL(url, description, severity string) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.URLs[strings.ToLower(url)] = IOC{
		Value:       strings.ToLower(url),
		Type:        TypeURL,
		Description: description,
		Severity:    severity,
	}
}

// ClearAll clears all IOCs
func (m *Manager) ClearAll() {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.IPAddresses = make(map[string]IOC)
	m.FileHashes = make(map[string]IOC)
	m.URLs = make(map[string]IOC)
}

// GetVersion returns the current IOC version
func (m *Manager) GetVersion() int64 {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.Version
}

// SetVersion sets the IOC version
func (m *Manager) SetVersion(version int64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.Version = version
}

// CheckIP checks if an IP address matches any IOC
func (m *Manager) CheckIP(ip string) (bool, IOC) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if ioc, ok := m.IPAddresses[ip]; ok {
		return true, ioc
	}
	return false, IOC{}
}

// CheckFileHash checks if a file hash matches any IOC
func (m *Manager) CheckFileHash(hash string) (bool, IOC) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	hash = strings.ToLower(hash)
	if ioc, ok := m.FileHashes[hash]; ok {
		return true, ioc
	}
	return false, IOC{}
}

// CheckURL checks if a URL matches any IOC
func (m *Manager) CheckURL(url string) (bool, IOC) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	url = strings.ToLower(url)

	// Exact match check
	if ioc, ok := m.URLs[url]; ok {
		return true, ioc
	}

	// Partial match check (URL contains IOC)
	for iocURL, ioc := range m.URLs {
		if strings.Contains(url, iocURL) {
			return true, ioc
		}
	}

	return false, IOC{}
}

// GetStats returns statistics about the IOC database
func (m *Manager) GetStats() map[string]interface{} {
	m.mu.RLock()
	defer m.mu.RUnlock()

	return map[string]interface{}{
		"version":       m.Version,
		"ip_count":      len(m.IPAddresses),
		"file_count":    len(m.FileHashes),
		"url_count":     len(m.URLs),
		"total_count":   len(m.IPAddresses) + len(m.FileHashes) + len(m.URLs),
	}
} 