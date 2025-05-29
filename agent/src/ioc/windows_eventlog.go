// +build windows

package ioc

import (
	"fmt"
	"log"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

// Windows Event Log API constants
const (
	EVENTLOG_SEQUENTIAL_READ = 0x0001
	EVENTLOG_FORWARDS_READ   = 0x0004
	EVENTLOG_BACKWARDS_READ  = 0x0008
	EVENTLOG_SEEK_READ       = 0x0002
)

// EVENTLOGRECORD structure for Windows Event Log
type EVENTLOGRECORD struct {
	Length              uint32
	Reserved            uint32
	RecordNumber        uint32
	TimeGenerated       uint32
	TimeWritten         uint32
	EventID             uint32
	EventType           uint16
	NumStrings          uint16
	EventCategory       uint16
	ReservedFlags       uint16
	ClosingRecordNumber uint32
	StringOffset        uint32
	UserSidLength       uint32
	UserSidOffset       uint32
	DataLength          uint32
	DataOffset          uint32
}

// Windows API functions
var (
	advapi32                = windows.NewLazySystemDLL("advapi32.dll")
	procOpenEventLogW       = advapi32.NewProc("OpenEventLogW")
	procReadEventLogW       = advapi32.NewProc("ReadEventLogW")
	procCloseEventLog       = advapi32.NewProc("CloseEventLog")
	procGetNumberOfEventLogRecords = advapi32.NewProc("GetNumberOfEventLogRecords")
	procGetOldestEventLogRecord    = advapi32.NewProc("GetOldestEventLogRecord")
)

// WindowsEventLogReader provides efficient access to Windows Event Logs
type WindowsEventLogReader struct {
	handle          windows.Handle
	lastRecordRead  uint32
	logName         string
}

// NewWindowsEventLogReader creates a new Windows Event Log reader
func NewWindowsEventLogReader(logName string) (*WindowsEventLogReader, error) {
	logNamePtr, err := windows.UTF16PtrFromString(logName)
	if err != nil {
		return nil, fmt.Errorf("failed to convert log name: %v", err)
	}
	
	ret, _, err := procOpenEventLogW.Call(
		0, // lpUNCServerName (local machine)
		uintptr(unsafe.Pointer(logNamePtr)),
	)
	
	if ret == 0 {
		return nil, fmt.Errorf("failed to open event log: %v", err)
	}
	
	return &WindowsEventLogReader{
		handle:         windows.Handle(ret),
		lastRecordRead: 0,
		logName:        logName,
	}, nil
}

// Close closes the event log handle
func (r *WindowsEventLogReader) Close() error {
	if r.handle != 0 {
		ret, _, err := procCloseEventLog.Call(uintptr(r.handle))
		if ret == 0 {
			return fmt.Errorf("failed to close event log: %v", err)
		}
		r.handle = 0
	}
	return nil
}

// GetEventCount returns the total number of events in the log
func (r *WindowsEventLogReader) GetEventCount() (uint32, error) {
	var count uint32
	ret, _, err := procGetNumberOfEventLogRecords.Call(
		uintptr(r.handle),
		uintptr(unsafe.Pointer(&count)),
	)
	
	if ret == 0 {
		return 0, fmt.Errorf("failed to get event count: %v", err)
	}
	
	return count, nil
}

// GetOldestRecordNumber returns the record number of the oldest event
func (r *WindowsEventLogReader) GetOldestRecordNumber() (uint32, error) {
	var oldest uint32
	ret, _, err := procGetOldestEventLogRecord.Call(
		uintptr(r.handle),
		uintptr(unsafe.Pointer(&oldest)),
	)
	
	if ret == 0 {
		return 0, fmt.Errorf("failed to get oldest record number: %v", err)
	}
	
	return oldest, nil
}

// ReadEvents reads events from the log starting from a specific record number
func (r *WindowsEventLogReader) ReadEvents(startRecord uint32, maxEvents int) ([]SysmonEvent, error) {
	var events []SysmonEvent
	buffer := make([]byte, 64*1024) // 64KB buffer
	
	var bytesRead uint32
	var minBytesNeeded uint32
	
	// Read events in chunks
	for len(events) < maxEvents {
			ret, _, _ := procReadEventLogW.Call(
		uintptr(r.handle),
		EVENTLOG_SEEK_READ|EVENTLOG_FORWARDS_READ,
		uintptr(startRecord),
		uintptr(unsafe.Pointer(&buffer[0])),
		uintptr(len(buffer)),
		uintptr(unsafe.Pointer(&bytesRead)),
		uintptr(unsafe.Pointer(&minBytesNeeded)),
	)
	
	if ret == 0 {
		// Check if we need a larger buffer
		if windows.GetLastError() == windows.ERROR_INSUFFICIENT_BUFFER {
			buffer = make([]byte, minBytesNeeded)
			continue
		}
		// No more events or other error
		break
	}
		
		// Parse events from buffer
		parsedEvents := r.parseEventsFromBuffer(buffer[:bytesRead])
		events = append(events, parsedEvents...)
		
		if len(parsedEvents) == 0 {
			break
		}
		
		// Update start record for next iteration
		lastEvent := parsedEvents[len(parsedEvents)-1]
		startRecord = lastEvent.RecordNumber + 1
	}
	
	return events, nil
}

// SysmonEvent represents a parsed Sysmon event
type SysmonEvent struct {
	RecordNumber  uint32
	EventID       uint32
	TimeGenerated time.Time
	ProcessName   string
	ProcessID     uint32
	Image         string
	Hashes        string
	TargetFilename string
	SourceImage   string
	TargetImage   string
	CommandLine   string
}

// parseEventsFromBuffer parses EVENTLOGRECORD structures from buffer
func (r *WindowsEventLogReader) parseEventsFromBuffer(buffer []byte) []SysmonEvent {
	var events []SysmonEvent
	offset := 0
	
	for offset < len(buffer) {
		if offset+int(unsafe.Sizeof(EVENTLOGRECORD{})) > len(buffer) {
			break
		}
		
		// Parse EVENTLOGRECORD header
		record := (*EVENTLOGRECORD)(unsafe.Pointer(&buffer[offset]))
		
		if record.Length == 0 || offset+int(record.Length) > len(buffer) {
			break
		}
		
		// Check if this is a Sysmon event (EventID 1, 11, 15, 23, 29)
		eventID := record.EventID & 0xFFFF // Lower 16 bits contain the actual event ID
		if r.isSysmonEventOfInterest(eventID) {
			event := r.parseSysmonEvent(record, buffer[offset:offset+int(record.Length)])
			if event != nil {
				events = append(events, *event)
			}
		}
		
		offset += int(record.Length)
	}
	
	return events
}

// isSysmonEventOfInterest checks if the event ID is one we care about
func (r *WindowsEventLogReader) isSysmonEventOfInterest(eventID uint32) bool {
	switch eventID {
	case 1:  // Process creation
		return true
	case 11: // File creation
		return true
	case 15: // File create stream hash
		return true
	case 23: // File delete
		return true
	case 29: // Remote thread creation
		return true
	default:
		return false
	}
}

// parseSysmonEvent parses a Sysmon event from the raw event data
func (r *WindowsEventLogReader) parseSysmonEvent(record *EVENTLOGRECORD, eventData []byte) *SysmonEvent {
	event := &SysmonEvent{
		RecordNumber:  record.RecordNumber,
		EventID:       record.EventID & 0xFFFF,
		TimeGenerated: time.Unix(int64(record.TimeGenerated), 0),
	}
	
	// Parse strings from the event data
	// The strings start at StringOffset and there are NumStrings of them
	if record.StringOffset > 0 && int(record.StringOffset) < len(eventData) {
		stringData := eventData[record.StringOffset:]
		strings := r.parseEventStrings(stringData, int(record.NumStrings))
		
		// Map strings to event fields based on EventID
		r.mapStringsToEvent(event, strings)
	}
	
	return event
}

// parseEventStrings parses null-terminated UTF-16 strings from event data
func (r *WindowsEventLogReader) parseEventStrings(data []byte, numStrings int) []string {
	var strings []string
	offset := 0
	
	for i := 0; i < numStrings && offset < len(data); i++ {
		// Find the end of the current string (null terminator)
		end := offset
		for end+1 < len(data) && (data[end] != 0 || data[end+1] != 0) {
			end += 2
		}
		
		if end > offset {
			// Convert UTF-16 to string
			utf16Data := make([]uint16, (end-offset)/2)
			for j := 0; j < len(utf16Data); j++ {
				utf16Data[j] = uint16(data[offset+j*2]) | uint16(data[offset+j*2+1])<<8
			}
			str := windows.UTF16ToString(utf16Data)
			strings = append(strings, str)
		}
		
		offset = end + 2 // Skip null terminator
	}
	
	return strings
}

// mapStringsToEvent maps parsed strings to event fields based on EventID
func (r *WindowsEventLogReader) mapStringsToEvent(event *SysmonEvent, strings []string) {
	// This is a simplified mapping - in reality, Sysmon events have complex XML structure
	// For production use, you'd need to parse the actual XML content or use a more sophisticated approach
	
	switch event.EventID {
	case 1: // Process creation
		if len(strings) > 4 {
			event.Image = strings[4]
		}
		if len(strings) > 2 {
			event.CommandLine = strings[2]
		}
		// Look for Hashes field in strings
		for _, str := range strings {
			if len(str) > 7 && str[:7] == "Hashes=" {
				event.Hashes = str[7:]
				break
			}
		}
		
	case 11: // File creation
		if len(strings) > 2 {
			event.TargetFilename = strings[2]
		}
		
	case 15: // File create stream hash
		if len(strings) > 2 {
			event.TargetFilename = strings[2]
		}
		// Look for Hash field
		for _, str := range strings {
			if len(str) > 5 && str[:5] == "Hash=" {
				event.Hashes = str[5:]
				break
			}
		}
		
	case 23: // File delete
		if len(strings) > 4 {
			event.Image = strings[4]
		}
		
	case 29: // Remote thread creation
		if len(strings) > 4 {
			event.SourceImage = strings[4]
		}
		if len(strings) > 5 {
			event.TargetImage = strings[5]
		}
	}
}

// scanWindowsSysmonLogsEfficient is the new efficient implementation
func (s *Scanner) scanWindowsSysmonLogsEfficient() error {
	log.Printf("Starting efficient Sysmon log scan using Windows Event Log API")
	
	// Open Sysmon event log
	reader, err := NewWindowsEventLogReader("Microsoft-Windows-Sysmon/Operational")
	if err != nil {
		return fmt.Errorf("failed to open Sysmon log: %v", err)
	}
	defer reader.Close()
	
	// Get total event count and oldest record number
	totalEvents, err := reader.GetEventCount()
	if err != nil {
		return fmt.Errorf("failed to get event count: %v", err)
	}
	
	oldestRecord, err := reader.GetOldestRecordNumber()
	if err != nil {
		return fmt.Errorf("failed to get oldest record: %v", err)
	}
	
	log.Printf("Sysmon log contains %d events, oldest record: %d", totalEvents, oldestRecord)
	
	// Calculate which record to start from based on last scan time
	// For simplicity, we'll read the last 1000 events or events since last scan
	startRecord := oldestRecord
	if s.lastRecordRead > 0 && s.lastRecordRead >= oldestRecord {
		startRecord = s.lastRecordRead + 1
	} else {
		// First run - start from recent events to avoid processing entire log
		if totalEvents > 1000 {
			startRecord = oldestRecord + totalEvents - 1000
		}
	}
	
	log.Printf("Reading events starting from record %d", startRecord)
	
	// Read events in batches
	const batchSize = 100
	eventsProcessed := 0
	
	for {
		events, err := reader.ReadEvents(startRecord, batchSize)
		if err != nil {
			log.Printf("Error reading events: %v", err)
			break
		}
		
		if len(events) == 0 {
			break
		}
		
		// Process each event
		for _, event := range events {
			s.processSysmonEvent(&event)
			eventsProcessed++
			
			// Update last record read
			if event.RecordNumber > s.lastRecordRead {
				s.lastRecordRead = event.RecordNumber
			}
		}
		
		// Update start record for next batch
		lastEvent := events[len(events)-1]
		startRecord = lastEvent.RecordNumber + 1
		
		log.Printf("Processed batch of %d events, total processed: %d", len(events), eventsProcessed)
	}
	
	log.Printf("Efficient Sysmon scan completed, processed %d events", eventsProcessed)
	return nil
}

// processSysmonEvent processes a single Sysmon event
func (s *Scanner) processSysmonEvent(event *SysmonEvent) {
	switch event.EventID {
	case 1: // Process creation
		if event.Hashes != "" {
			s.processHashesData(event.Hashes, event.Image)
		}
		
	case 11: // File creation
		if event.TargetFilename != "" {
			// Calculate hash for the created file
			hashValue, err := s.calculateFileHash(event.TargetFilename)
			if err == nil {
				match, ioc := s.manager.CheckFileHash(hashValue)
				if match {
					s.handleMaliciousFile(event.TargetFilename, hashValue, &ioc)
				}
			}
		}
		
	case 15: // File create stream hash
		if event.Hashes != "" && event.TargetFilename != "" {
			s.processHashesData(event.Hashes, event.TargetFilename)
		}
		
	case 23: // File delete
		if event.Hashes != "" {
			s.processHashesData(event.Hashes, event.Image)
		}
		
	case 29: // Remote thread creation
		// Check both source and target processes
		if event.SourceImage != "" {
			sourceHash, err := s.calculateFileHash(event.SourceImage)
			if err == nil {
				match, ioc := s.manager.CheckFileHash(sourceHash)
				if match {
					log.Printf("Malicious process creating remote thread: %s (%s)", event.SourceImage, sourceHash)
					s.handleMaliciousFile(event.SourceImage, sourceHash, &ioc)
				}
			}
		}
		
		if event.TargetImage != "" {
			targetHash, err := s.calculateFileHash(event.TargetImage)
			if err == nil {
				match, ioc := s.manager.CheckFileHash(targetHash)
				if match {
					log.Printf("Remote thread created in malicious process: %s (%s)", event.TargetImage, targetHash)
					s.handleMaliciousFile(event.TargetImage, targetHash, &ioc)
				}
			}
		}
		
		log.Printf("Remote thread created from %s to %s", event.SourceImage, event.TargetImage)
	}
} 