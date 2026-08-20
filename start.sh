#!/bin/bash

# ETPF Startup Script for Unix/macOS/Linux (and Git Bash)

# Color codes
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

echo -e "${CYAN}Starting database container (PostgreSQL)...${RESET}"
docker compose up -d
if [ $? -ne 0 ]; then
    echo -e "${RED}Warning: Failed to start Docker container. Please check if Docker is running.${RESET}"
fi

# Function to stop background processes on exit
cleanup() {
    echo -e "\n${YELLOW}Stopping services...${RESET}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}
trap cleanup SIGINT SIGTERM

# Start Backend in the background
echo -e "${CYAN}Starting FastAPI backend...${RESET}"
if [ -d "backend/.venv" ]; then
    source backend/.venv/bin/activate
fi
cd backend
python run.py &
BACKEND_PID=$!
cd ..

# Start Frontend in the background
echo -e "${CYAN}Starting Vite frontend...${RESET}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo -e "\n${GREEN}All services are running in the background!${RESET}"
echo -e "${GREEN}- Database: localhost:5432${RESET}"
echo -e "${GREEN}- Backend API: http://localhost:8000${RESET}"
echo -e "${GREEN}- Frontend Client: http://localhost:5173${RESET}"
echo -e "\n${YELLOW}Press Ctrl+C to stop both backend and frontend.${RESET}"

# Keep script running to show logs/keep background jobs alive
wait
