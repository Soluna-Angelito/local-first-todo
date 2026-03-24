Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

dir = fso.GetParentFolderName(WScript.ScriptFullName)

batPath = dir & "\1 run_server - without console.bat"
logPath = dir & "\server.log"

cmd = "cmd.exe /c " & Chr(34) & Chr(34) & batPath & Chr(34) & " > " & Chr(34) & logPath & Chr(34) & " 2>&1" & Chr(34)

sh.CurrentDirectory = dir
sh.Run cmd, 0, False
