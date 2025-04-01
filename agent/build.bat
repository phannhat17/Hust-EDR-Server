@echo off
setlocal

echo Building EDR Agent...

REM Check if protoc is installed
WHERE protoc >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: protoc (Protocol Buffers compiler) is not installed
    echo Please install it from https://github.com/protocolbuffers/protobuf/releases
    exit /b 1
)

REM Check if Go is installed
WHERE go >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Go is not installed
    echo Please install it from https://golang.org/dl/
    exit /b 1
)

REM Install protoc-gen-go and protoc-gen-go-grpc if not already installed
go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.28
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.2

REM Update PATH to include Go bin directory
set PATH=%PATH%;%USERPROFILE%\go\bin

REM Generate Go code from Protocol Buffers definition
echo Generating gRPC code...
cd proto
protoc --go_out=. --go_opt=paths=source_relative --go-grpc_out=. --go-grpc_opt=paths=source_relative agent.proto
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to generate gRPC code
    exit /b 1
)
cd ..

REM Download dependencies
echo Downloading dependencies...
go mod tidy
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to download dependencies
    exit /b 1
)

REM Build agent for Windows
echo Building agent executable...
go build -o edr-agent.exe .
if %ERRORLEVEL% NEQ 0 (
    echo Error: Build failed
    exit /b 1
)

echo Build completed successfully.
echo executable: edr-agent.exe

endlocal 