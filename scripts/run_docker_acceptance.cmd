@echo off
setlocal EnableDelayedExpansion

set "ROOT=%~dp0.."
set "DOCKER=C:\Program Files\Docker\Docker\resources\bin\docker.exe"
set "HOST_PORT=18000"
set "LOG=%ROOT%\reports\docker-acceptance.log"
set "COMPLETE=%ROOT%\reports\docker-acceptance.complete"
set "HEALTH_FILE=%ROOT%\reports\docker-health-status.txt"

cd /d "%ROOT%"
del /q "%COMPLETE%" >nul 2>&1
if exist ".pytest_cache" rmdir /s /q ".pytest_cache" >nul 2>&1

echo ==== Docker acceptance started %DATE% %TIME% ==== > "%LOG%"
"%DOCKER%" version >> "%LOG%" 2>&1
"%DOCKER%" compose config >> "%LOG%" 2>&1

"%DOCKER%" image inspect python:3.12-slim >nul 2>&1
if not errorlevel 1 goto base_ready

for %%M in (
  docker.m.daocloud.io/library/python:3.12-slim
  docker.1ms.run/library/python:3.12-slim
  dockerpull.org/library/python:3.12-slim
) do (
  echo Trying base image mirror %%M >> "%LOG%"
  "%DOCKER%" pull %%M >> "%LOG%" 2>&1
  if not errorlevel 1 (
    "%DOCKER%" tag %%M python:3.12-slim >> "%LOG%" 2>&1
    if not errorlevel 1 goto base_ready
  )
)

echo ERROR: unable to obtain python:3.12-slim from configured mirrors >> "%LOG%"
goto capture

:base_ready
echo Base image available: python:3.12-slim >> "%LOG%"
set "DOCKER_BUILDKIT=0"
"%DOCKER%" compose up -d --build >> "%LOG%" 2>&1

set "HEALTH=starting"
for /L %%I in (1,1,60) do (
  "%DOCKER%" inspect --format="{{.State.Health.Status}}" ai-security-intelligence-workbench > "%HEALTH_FILE%" 2>nul
  set /p HEALTH=<"%HEALTH_FILE%"
  if "!HEALTH!"=="healthy" goto healthy
  timeout /t 2 /nobreak >nul
)

goto capture

:healthy
echo ==== Container healthy ==== >> "%LOG%"

:capture
"%DOCKER%" compose ps >> "%LOG%" 2>&1
"%DOCKER%" inspect ai-security-intelligence-workbench >> "%LOG%" 2>&1
curl.exe -fsS http://127.0.0.1:%HOST_PORT%/api/health >> "%LOG%" 2>&1
echo. >> "%LOG%"
"%DOCKER%" compose logs --no-color >> "%LOG%" 2>&1
echo ==== Docker acceptance finished %DATE% %TIME% ==== >> "%LOG%"
echo %HEALTH% > "%COMPLETE%"
exit /b 0
