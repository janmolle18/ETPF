# ETPF Startup Script for Windows (PowerShell)

# 1. Start the PostgreSQL database using Docker Compose
Write-Host "Starting database container (PostgreSQL)..." -ForegroundColor Cyan
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Failed to start Docker container. Please make sure Docker Desktop is running."
}

# 2. Start the Backend in a new window
Write-Host "Starting FastAPI backend in a new window..." -ForegroundColor Cyan
if (Test-Path "backend\.venv") {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; .\.venv\Scripts\Activate.ps1; python run.py"
} else {
    Write-Warning "Backend virtual environment (.venv) not found. Starting backend without activating it..."
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; python run.py"
}

# 3. Start the Frontend in a new window
Write-Host "Starting Vite frontend in a new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "`nAll services have been triggered!" -ForegroundColor Green
Write-Host "- Database: localhost:5432" -ForegroundColor Green
Write-Host "- Backend API: http://localhost:8000" -ForegroundColor Green
Write-Host "- Frontend Client: http://localhost:5173" -ForegroundColor Green
Write-Host "`nKeep the opened PowerShell windows running to view logs. Close them to stop services." -ForegroundColor Yellow
