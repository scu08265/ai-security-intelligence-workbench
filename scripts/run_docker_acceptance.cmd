@echo off
setlocal EnableDelayedExpansion

rem Step 1 of the local container acceptance: build the image, start the Compose
rem stack, wait for the container health check and capture the raw log.
rem Step 2 is tools/build_docker_validation.py, which turns the live container
rem state into reports/docker-validation.json and asserts the reported version.

set "ROOT=%~dp0.."
set "HOST_PORT=18000"
set "IMAGE=ai-security-intelligence-workbench"
set "LOG=%ROOT%\reports\docker-acceptance.log"
set "COMPLETE=%ROOT%\reports\docker-acceptance.complete"
set "HEALTH_FILE=%ROOT%\reports\docker-health-status.txt"

cd /d "%ROOT%"

rem Never let a real credential reach an artifact that gets committed.
rem `docker compose config` prints the resolved environment and `docker inspect`
rem prints the container's Env, so a populated .env would otherwise be copied
rem verbatim into reports/docker-acceptance.log.  Compose interpolates from
rem ./.env by default -- clearing the shell variable is not enough, because an
rem absent variable simply makes Compose fall back to the file.  Pointing
rem --env-file at a scratch file removes that source entirely; the shell
rem environment still supplies APP_VERSION.
set "GITHUB_TOKEN="
set "DEEPSEEK_API_KEY="
set "INTEL_ALERT_WEBHOOK_URL="
set "ACCEPTANCE_ENV=%TEMP%\docker-acceptance-no-credentials.env"
> "%ACCEPTANCE_ENV%" echo # docker acceptance: intentionally exposes no credentials

rem The install drive is not fixed: this team has the CLI under D:\Docker while a
rem default install puts it under C:\Program Files.  Try PATH first.
set "DOCKER="
for %%D in (docker.exe) do if not defined DOCKER set "DOCKER=%%~$PATH:D"
if not defined DOCKER if exist "D:\Docker\Docker\resources\bin\docker.exe" set "DOCKER=D:\Docker\Docker\resources\bin\docker.exe"
if not defined DOCKER if exist "C:\Program Files\Docker\Docker\resources\bin\docker.exe" set "DOCKER=C:\Program Files\Docker\Docker\resources\bin\docker.exe"
if not defined DOCKER (
  echo ERROR: docker CLI not found on PATH or in a known install location
  exit /b 1
)

rem VERSION is the single source of truth.  CI builds with the same --build-arg,
rem and step 2 asserts the container reports this exact version.
set "APP_VERSION="
for /f "usebackq delims=" %%V in ("%ROOT%\VERSION") do if not defined APP_VERSION set "APP_VERSION=%%V"
if not defined APP_VERSION (
  echo ERROR: %ROOT%\VERSION is empty or missing
  exit /b 1
)

del /q "%COMPLETE%" >nul 2>&1
del /q "%HEALTH_FILE%" >nul 2>&1
if exist ".pytest_cache" rmdir /s /q ".pytest_cache" >nul 2>&1

echo ==== Docker acceptance started %DATE% %TIME% ==== > "%LOG%"
echo docker CLI: %DOCKER% >> "%LOG%"
echo APP_VERSION: %APP_VERSION% >> "%LOG%"
"%DOCKER%" version >> "%LOG%" 2>&1
"%DOCKER%" compose --env-file "%ACCEPTANCE_ENV%" config >> "%LOG%" 2>&1

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
"%DOCKER%" build --build-arg APP_VERSION=%APP_VERSION% -t "%IMAGE%:%APP_VERSION%" . >> "%LOG%" 2>&1
"%DOCKER%" compose --env-file "%ACCEPTANCE_ENV%" up -d >> "%LOG%" 2>&1

set "HEALTH=starting"
for /L %%I in (1,1,60) do (
  "%DOCKER%" inspect --format="{{.State.Health.Status}}" %IMAGE% > "%HEALTH_FILE%" 2>nul
  set /p HEALTH=<"%HEALTH_FILE%"
  if "!HEALTH!"=="healthy" goto healthy
  rem `timeout` refuses to run when stdin is redirected (CI, scheduled task,
  rem piped shell), so wait with ping instead: -n 3 is roughly two seconds.
  ping -n 3 127.0.0.1 >nul
)

goto capture

:healthy
echo ==== Container healthy ==== >> "%LOG%"

:capture
"%DOCKER%" compose --env-file "%ACCEPTANCE_ENV%" ps >> "%LOG%" 2>&1
"%DOCKER%" inspect %IMAGE% >> "%LOG%" 2>&1
curl.exe -fsS http://127.0.0.1:%HOST_PORT%/api/health >> "%LOG%" 2>&1
echo. >> "%LOG%"
"%DOCKER%" compose --env-file "%ACCEPTANCE_ENV%" logs --no-color >> "%LOG%" 2>&1
echo ==== Docker acceptance finished %DATE% %TIME% ==== >> "%LOG%"
echo %HEALTH% > "%COMPLETE%"
del /q "%HEALTH_FILE%" >nul 2>&1
del /q "%ACCEPTANCE_ENV%" >nul 2>&1
exit /b 0
