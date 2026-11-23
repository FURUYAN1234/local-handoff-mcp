@echo off
"%SystemRoot%\System32\wsl.exe" -d Ubuntu --exec /usr/bin/python3 -B -c "from pathlib import Path; import os,sys; entry=Path.home()/'.local/share/local-handoff-mcp/launch.py'; os.execv(sys.executable,[sys.executable,'-B',str(entry),'--open','dashboard'])"
if errorlevel 1 pause
