@echo off
chcp 437 >nul
echo ==== Windows System Check ====
echo.

REM Computer name
echo Computer name:
hostname
echo.

REM Windows version
echo Windows version:
ver
echo.

REM RAM info
echo Physical memory:
systeminfo | findstr /C:"Total Physical Memory"
echo.

REM CPU load
echo CPU load (current processes):
wmic cpu get loadpercentage
echo.

REM Free disk space
echo Free disk space:
wmic logicaldisk get name,freespace,size
echo.

REM Internet connectivity check
echo Internet connectivity check (ping google.com):
ping -n 2 google.com >nul
if %errorlevel%==0 (
    echo Internet: available
) else (
    echo Internet: unavailable
)
echo.


python -V
pip -V

echo.
echo.
echo Did you want to install libraries?
pause


