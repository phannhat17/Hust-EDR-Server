# Build stage
FROM golang:1.20-alpine AS builder

WORKDIR /app

# Install required packages
RUN apk add --no-cache git protobuf protobuf-dev

# Install required Go tools
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.28 && \
    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.2

# Copy go.mod and go.sum
COPY go.mod ./

# Download dependencies
RUN go mod download

# Copy proto files
COPY proto/ ./proto/

# Generate gRPC code
RUN protoc --go_out=. --go_opt=paths=source_relative \
           --go-grpc_out=. --go-grpc_opt=paths=source_relative \
           proto/agent.proto

# Copy source code
COPY . .

# Build the agent
RUN CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -o edr-agent.exe .

# Final image
FROM scratch

WORKDIR /

# Copy binary from builder
COPY --from=builder /app/edr-agent.exe /edr-agent.exe

# The image will be used to extract the executable
ENTRYPOINT [] 