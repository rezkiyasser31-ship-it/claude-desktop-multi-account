Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
appPath = currentDir & "\app.py"
WshShell.Run "pythonw """ & appPath & """", 0, False
