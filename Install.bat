@echo off
setlocal
wsl.exe -d Ubuntu --exec /usr/bin/python3 -B -c "import os,sys; from pathlib import Path,PureWindowsPath; w=PureWindowsPath(sys.argv[1]); root=Path('/mnt',w.drive[0].lower()) if len(w.drive)==2 else Path('/'); p=root.joinpath(*w.parts[1:]).with_name('install.py'); os.execv(sys.executable,[sys.executable,'-B',str(p),'--windows-home',sys.argv[2],*sys.argv[3:]])" "%~f0" "%USERPROFILE%" %*
set "result=%errorlevel%"
if not "%result%"=="0" echo Installation stopped. See the message above.
if "%~1"=="" pause
exit /b %result%
