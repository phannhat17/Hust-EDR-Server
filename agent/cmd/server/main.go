package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"

	pb "github.com/hustonpi/edr-agent/proto"
	"google.golang.org/grpc"
)

var (
	port = flag.Int("port", 50051, "Server port")
)

// AgentServer implements the AgentService
type AgentServer struct {
	pb.UnimplementedAgentServiceServer
}

// SendMachineInfo handles machine information requests from agents
func (s *AgentServer) SendMachineInfo(ctx context.Context, req *pb.MachineInfoRequest) (*pb.MachineInfoResponse, error) {
	log.Printf("Received machine info from: %s (%s)", req.Hostname, req.IpAddress)
	
	// Display detailed information if available
	if req.OsVersion != "" {
		log.Printf("OS: %s", req.OsVersion)
		log.Printf("CPU: %s", req.CpuInfo)
		log.Printf("Memory: %d MB total, %d MB free", req.TotalMemory/1024/1024, req.FreeMemory/1024/1024)
		log.Printf("Agent version: %s", req.AgentVersion)
		
		for i, disk := range req.Disks {
			log.Printf("Disk %d: %s (%s) - %d GB total, %d GB free", 
				i+1, disk.DriveLetter, disk.FileSystem, 
				disk.TotalSize/1024/1024/1024, disk.FreeSpace/1024/1024/1024)
		}
	}
	
	return &pb.MachineInfoResponse{
		Success: true,
		Message: fmt.Sprintf("Successfully received information from %s", req.Hostname),
	}, nil
}

func main() {
	flag.Parse()
	
	// Create a TCP listener
	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}
	
	// Create a gRPC server
	grpcServer := grpc.NewServer()
	
	// Register the AgentService
	pb.RegisterAgentServiceServer(grpcServer, &AgentServer{})
	
	// Handle graceful shutdown
	go func() {
		sigChan := make(chan os.Signal, 1)
		signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
		<-sigChan
		log.Println("Shutting down server...")
		grpcServer.GracefulStop()
	}()
	
	// Start the server
	log.Printf("Starting test server on port %d...", *port)
	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
} 