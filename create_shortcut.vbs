Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = oWS.SpecialFolders("Desktop") & "\Birthright Campaign Manager.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "pythonw.exe"
oLink.Arguments = "-m oracle.gui.launcher"
oLink.WorkingDirectory = "C:\Users\caleb\oracle"
oLink.Description = "Birthright Campaign Manager"
oLink.Save
WScript.Echo "Shortcut created on desktop!"
