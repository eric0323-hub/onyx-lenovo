### Symptom

The Windows Start button or the taskbar does not work and becomes unresponsive.

### Applicable Brands

* ideapad
* ideacentre

### Operating Systems

* Windows 10
* Windows 11

### Solution

Windows Explorer is the default file manager in Windows and it allows you to see, interact with, and modify files present on your system. Sometimes problems with Windows Explorer can cause the Start button or the taskbar to become unresponsive. Restarting Windows Explorer can often resolve this problem. If nothing happens when clicking the Start button, or if the entire taskbar does not respond to interactions, Windows Explorer needs to be restarted.

Click here for **[Method 1](#method1)** for how to restart Windows Explorer. Sometimes problems with Windows Explorer become so severe that it cannot be restarted from Task Manager. When this happens, click here for **[Method 2](#method2)** to restart Windows Explorer and to reset the taskbar.

**Method 1: Restarting Windows Explorer Via Task Manager**

1. PressCtrl + Alt + Delete on the keyboard to bring up **Task Manager**.  
   ![Task Manager](https://download.lenovo.com/km/media/images/HT503047/taskmanagerdesktop_20241218162737559.png)
2. Locate Windows Explorer in the task list under the **Process** tab, and click the **Restart** button, or right-click the Windows Explorer task and select **Restart**.  
   ![Processes](https://download.lenovo.com/km/media/images/HT503047/startbuttonnotrespond_20161227065743.PNG)  
     
   ![Restart](https://download.lenovo.com/km/media/images/HT503047/TaskManagerrestart_20220302181510921.png)
  
4. Sometimes Task Manager itself also becomes unresponsive to actions. When this happens, see [**Method 2**](method2).

**Method 2: Restarting the taskbar using taskkill command in command prompt**

1. Press Windows key + r and enter **cmd** in the Run box to open a Windows **Command Prompt** window.  
   ![cmd](https://download.lenovo.com/km/media/images/HT503047/cmd_20230511094456884.png)
2. To end Windows Explorer, type the **taskkill** command with **/f**, **/im** options and the **start** command to reset the taskbar.
3. Open a command prompt and enter the command:  
   `taskkill /f /im explorer.exe && start explorer.exe`  
   ![cmd](https://download.lenovo.com/km/media/images/HT503047/restart_cmd_20230511100801769.png)
4. The command will forcefully restart Windows Explorer and reset the Taskbar. Command prompt runs the command as shown in the following image.  
   ![cmd2](https://download.lenovo.com/km/media/images/HT503047/cmd(2)_20230511100214103.png)​
5. Taskbar should be reset or restarted.  
   ![restart](https://download.lenovo.com/km/media/images/HT503047/cmd(3)_20230511101008122.png)
6. Click the **Start** button and Taskbar to try it again.  
   ![button](https://download.lenovo.com/km/media/images/HT503047/start_button_20230511101043947.png)

### Related Articles

* [Popular Topics: Tips for PC's](https://support.lenovo.com/solutions/ht503909)
* [Popular Topics: Windows 11, 10](https://pcsupport.lenovo.com/solutions/ht118590)
* [Microsoft - Customize the Taskbar in Windows](https://support.microsoft.com/en-us/windows/customize-the-taskbar-in-windows-0657a50f-0cc7-dbfd-ae6b-05020b195b07#ID0EDD=Windows_11&windowsversion=windows_11)
* [How to find and view manuals for Lenovo products](https://support.lenovo.com/us/en/solutions/ht077589-how-to-find-and-view-manuals-for-lenovo-products-thinkpad-thinkcentre-ideapad-ideacentre)
