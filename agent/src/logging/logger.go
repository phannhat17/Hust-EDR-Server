package logging

import (
	"io"
	"os"
	"strings"
	"time"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"

	"agent/config"
)

// Global logger instance
var Logger zerolog.Logger

// InitLogger initializes the global logger based on configuration
func InitLogger(cfg *config.Config) error {
	// Set global log level
	level, err := zerolog.ParseLevel(strings.ToLower(cfg.LogLevel))
	if err != nil {
		level = zerolog.InfoLevel // Default to info if invalid level
	}
	zerolog.SetGlobalLevel(level)

	// Configure output writers
	var writers []io.Writer

	// Console output (always enabled)
	if cfg.LogFormat == "json" {
		writers = append(writers, os.Stdout)
	} else {
		// Pretty console output
		consoleWriter := zerolog.ConsoleWriter{
			Out:        os.Stdout,
			TimeFormat: time.RFC3339,
			NoColor:    false,
		}
		writers = append(writers, consoleWriter)
	}

	// File output (if specified)
	if cfg.LogFile != "" {
		file, err := os.OpenFile(cfg.LogFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
		if err != nil {
			return err
		}
		
		if cfg.LogFormat == "json" {
			writers = append(writers, file)
		} else {
			// Use JSON format for file even if console is pretty
			writers = append(writers, file)
		}
	}

	// Create multi-writer if multiple outputs
	var output io.Writer
	if len(writers) == 1 {
		output = writers[0]
	} else {
		output = zerolog.MultiLevelWriter(writers...)
	}

	// Create logger with timestamp and caller info
	Logger = zerolog.New(output).With().
		Timestamp().
		Caller().
		Str("component", "edr-agent").
		Logger()

	// Set as global logger
	log.Logger = Logger

	Logger.Info().
		Str("log_level", cfg.LogLevel).
		Str("log_format", cfg.LogFormat).
		Str("log_file", cfg.LogFile).
		Msg("Logger initialized")

	return nil
}

// GetLogger returns the global logger instance
func GetLogger() zerolog.Logger {
	return Logger
}

// Info logs an info message
func Info() *zerolog.Event {
	return Logger.Info()
}

// Error logs an error message
func Error() *zerolog.Event {
	return Logger.Error()
}

// Warn logs a warning message
func Warn() *zerolog.Event {
	return Logger.Warn()
}

// Debug logs a debug message
func Debug() *zerolog.Event {
	return Logger.Debug()
}

// Fatal logs a fatal message and exits
func Fatal() *zerolog.Event {
	return Logger.Fatal()
}

// With creates a child logger with additional fields
func With() zerolog.Context {
	return Logger.With()
} 