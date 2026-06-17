Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set objShell = CreateObject("Wscript.Shell")
objShell.CurrentDirectory = currentDir

' Build absolute paths with double quotes to handle folder spaces
pythonPath = """" & currentDir & "\venv\Scripts\python.exe"""
scriptPath = """" & currentDir & "\dashboard.py"""

' Execute Python directly without cmd /c to prevent quote-stripping issues in cmd.exe
objShell.Run pythonPath & " -m streamlit run " & scriptPath & " --server.headless true --browser.gatherUsageStats false --server.port 8501", 0, False
