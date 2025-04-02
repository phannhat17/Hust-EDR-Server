# HUST EDR Server

A modern Endpoint Detection and Response (EDR) system with a beautiful React frontend and Flask backend.

## Features

- Real-time security alerts from ElastAlert
- Rule management for detection and alerting
- Modern UI built with React, TanStack Router, and Shadcn UI components
- Secure API integration

## Project Structure

- `backend/`: Flask API server
  - Connects to Elasticsearch for alerts and rule management
  - Manages ElastAlert rules and configuration
  - Provides RESTful API endpoints

- `frontend/`: React application built with Vite
  - Modern UI with Shadcn components
  - TanStack Router for routing
  - TanStack Query for API data fetching
  - Type-safe integration with backend

## Setup and Installation

### Prerequisites

- Python 3.8+
- Node.js 16+ and npm/pnpm
- Elasticsearch instance
- ElastAlert container (optional, for rule execution)

### Backend Setup

1. Navigate to the backend directory
   ```
   cd backend
   ```

2. Create a virtual environment
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Configure environment variables in `.env` file (copy from `.env.example`)
   ```
   cp .env.example .env
   # Edit .env file with your configuration
   ```

5. Run the Flask development server
   ```
   flask run
   ```

### Frontend Setup

1. Navigate to the frontend directory
   ```
   cd frontend
   ```

2. Install dependencies
   ```
   pnpm install
   ```

3. Configure environment variables in `.env` file (copy from `.env.example`)
   ```
   cp .env.example .env
   # Edit .env file with your configuration
   ```

4. Run the development server
   ```
   npm run dev -- --host
   ```

## Development

For easier development, you can use the provided development script to start both frontend and backend:

```
./run_dev.sh
```

This script will:
1. Set up Python virtual environment if it doesn't exist
2. Install frontend dependencies if they don't exist
3. Start backend server on port 5000
4. Start frontend development server
5. Allow graceful shutdown of both with Ctrl+C

## API Documentation

The backend provides the following API endpoints:

- `GET /api/alerts`: Retrieve alerts from ElastAlert
- `PUT /api/alerts/<alert_id>`: Update an alert's status
- `GET /api/rules`: Get all ElastAlert rules
- `GET /api/rules/<filename>`: Get a specific rule
- `POST /api/rules`: Create a new rule
- `PUT /api/rules/<filename>`: Update an existing rule
- `DELETE /api/rules/<filename>`: Delete a rule
- `POST /api/elastalert/restart`: Restart the ElastAlert container

## License

This project is licensed under the MIT License - see the LICENSE file for details. 