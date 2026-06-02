@echo off
REM Remove root-owned files from local-dev\build (Docker pip leaves them on Windows).
REM Run from this folder:  clean_build.cmd

set "BUILD_DIR=%~dp0build"
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"

echo Cleaning %BUILD_DIR%
docker run --rm -v "%BUILD_DIR%:/build" alpine sh -c "rm -rf /build/*"
if errorlevel 1 exit /b 1
echo Done. Run build_zip.sh from Git Bash or WSL next.
