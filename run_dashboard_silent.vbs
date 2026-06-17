Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set objShell = CreateObject("Wscript.Shell")
objShell.CurrentDirectory = currentDir
objShell.Run "venv\Scripts\pythonw.exe -m streamlit run dashboard.py --server.headless true --browser.gatherUsageStats false --server.port 8501", 0, False
