@echo off
echo Building EDR Agent for Windows...

REM Set environment variables for Go to build for Windows
set GOOS=windows
set GOARCH=amd64

REM Generate gRPC code from proto files
echo Generating gRPC code...
protoc --go_out=. --go_opt=paths=source_relative --go-grpc_out=. --go-grpc_opt=paths=source_relative proto/agent.proto

REM Build the agent
echo Building agent...
go build -o bin/edr-agent.exe cmd/agent/main.go

echo Build completed!
echo The agent binary is located at: bin\edr-agent.exe 