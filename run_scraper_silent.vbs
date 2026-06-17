Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set objShell = CreateObject("Wscript.Shell")
objShell.CurrentDirectory = currentDir
objShell.Run "venv\Scripts\pythonw.exe job_pipeline.py", 0, False
