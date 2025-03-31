#!/bin/bash

# Install backend dependencies if they don't exist
if [ ! -d "backend/.venv" ]; then
  echo "Setting up backend virtual environment..."
  cd backend
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  cd ..
else
  echo "Backend virtual environment already exists"
fi

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
  echo "Installing frontend dependencies..."
  cd frontend
  npm install
  cd ..
else
  echo "Frontend dependencies already installed"
fi

# Start backend
echo "Starting backend server..."
cd backend
source .venv/bin/activate
python wsgi.py &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Starting frontend development server..."
cd frontend
npm run dev -- --host &
FRONTEND_PID=$!
cd ..

# Wait for user to press Ctrl+C
echo "Development servers started. Press Ctrl+C to stop all servers."
trap "kill $BACKEND_PID $FRONTEND_PID; exit 0" INT
wait 