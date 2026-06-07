### Symptom

The touchpad or trackpad is not responding to any gestures.

### Applicable Brands

ThinkPad

### Solution

Try the following options.

[Video] [Touchpad Not Working in Windows 10, 8, 7](https://support.lenovo.com/solutions/VID500014)

#### Use trackpoint or keyboard keys to make sure touchpad is enabled

**Make sure the Touchpad is enabled.**

If the touchpad is not working, use these steps to access Touchpad options:

1. Select the Windows logo key + I (capital i). Another option is to use Windows key + S.
2. Type **touchpad**.
3. Select the **Turn the touchpad on or off option** (use the arrow key to move down the list and Enter to select).  
   ![Touchpad settings](https://download.lenovo.com/km/media/images/HT075599/mousesettings_20200615184917225.png)
4. Make sure Touchpad is set to **On**. Use the Tab key to select the Touchpad option. Use the Spacebar key to toggle the option.  
   ![Touchpad](https://download.lenovo.com/km/media/images/SSTS100157/touch_20210826163818852.png)

**Note:** For additional information, see this Microsoft link: [Keyboard shortcuts in Windows](https://support.microsoft.com/windows/keyboard-shortcuts-in-windows-dcc61a57-8ff0-cffe-9796-cb9706c75eec).

The trackpoint can also be used to select and navigate in Windows. Check the user manual to see if the system has a trackpoint. For example:  
![Trackpoint button](https://download.lenovo.com/km/media/images/HT104456/redbutton_20210216151225811.png)

For information about finding user manuals, see [How to find and view manuals for Lenovo products - ThinkPad, ThinkCentre, ideapad, ideacentre](https://support.lenovo.com/solutions/ht077589).



#### Download current drivers

1. Download and install the latest Synaptics ThinkPad UltraNav Driver from [Lenovo Support Site](http://support.lenovo.com).  
   **Note**: Go to Lenovo Support Site and select the product first before downloading the driver.  
   
   Updates are also available with the automatic scan option:
   1. Go to <https://support.lenovo.com>.
   2. Select **Detect Product**.  
      ![Detect Product](https://download.lenovo.com/km/media/images/HT104456/detectproduct2024_20240715170630967.png)
   3. Select **Drivers & Software**.  
      ![Drivers and Software](https://download.lenovo.com/km/media/images/HT104456/driversandsoftware2024_2024100118233170.png)
   4. Select **Scan Now** under **Automatic Update** and scan for updates.  
      ![Automatic Update](https://download.lenovo.com/km/media/images/HT104456/automaticdriverupdateJan2023_20240506173939305.png)


#### Roll back the touchpad driver

If this used to work, consider rolling back the touchpad driver.

1. Search for and select **Device Manager** (use Windows key + S to search for Device Manager, use up or down arrow keys to move up or down the list and Enter to select).  
     
   ![Device Manager](https://download.lenovo.com/km/media/images/HT104456/Windows11Devicemansearch_2025071015552249.png)
2. Expand the **Mice and other pointing devices** category (use up or down arrow keys to move up or down the list of items, use the right or left arrow keys to expand or close the sub-item list).
3. Right-click the driver (or move to the driver with the arrow key and select Enter).
4. Select **Properties**.
5. Select **Roll Back Driver** under the **Driver** tab (use the left or right arrow keys to change tabs, use the tab key to move to Roll Back Driver, use Enter to select). If the menu option text is gray, there is no driver to roll back to.  
   ![Roll Back Driver](https://download.lenovo.com/km/media/images/HT104456/rollback1_20201102143516389.png)

If the touchpad driver is not visible in Device Manager:

1. Open Device Manager (use Windows key + S to search for Device Manager).  
   ![Device Manager](https://download.lenovo.com/km/media/images/HT104456/Windows11Devicemansearch_20260213141823214.png)
2. Select **View**, then **Show Hidden Devices** (use Alt + V to select the View tab menu, use down arrow to move to the menu option, and Enter to select).
3. Check under **Human Interface Devices** and see if the touchpad driver is grayed out (use up or down arrows to move up or down the list and left or right arrows to close or expand the sub-list). If so, highlight the driver and use the **Action** tab (alt + A). Click **Update driver** (use Enter to select the menu option).  
   ![Update driver](https://download.lenovo.com/km/media/images/HT104456/update5_20210112150351250.png)  
   **Note:** If the touchpad driver is still not visible, get the download from the product support page on the Lenovo site.
4. After updating the driver, try restarting Windows.


#### Increase touchpad sensitivity

Try to increase touchpad sensitivity. Visit the following url link [How to adjust Touchpad Sensitivity.](https://support.lenovo.com/solutions/ht075745)


#### Check the touchpad in safe mode

See the following links for more information:  
[How to enter safe mode in Windows](https://support.lenovo.com/solutions/ht105328) or [Windows Startup Settings](https://support.microsoft.com/windows/windows-startup-settings-1af6ec8c-4d4a-4b23-adb7-e76eef0b847f).

If the touchpad works in safe mode, then the issue is related to software or drivers.



#### Run keyboard troubleshooter

1. Select **Start** and **Settings**.  
   ![Settings](https://download.lenovo.com/km/media/images/HT104456/Windows11startsettings_20260213141933584.png)
2. Select **System,** **Troubleshoot**, **Other troubleshooters (**or **Additional troubleshooters)**.
3. Run the **Keyboard** troubleshooter. **Note**: Recent versions of Windows 11 may no longer have this option.  
   ![Keyboard](https://download.lenovo.com/km/media/images/HT104456/troubleshootkeyboard_20241217145809801.png)  
   
   ​For details, see [How to run Windows Troubleshooters - Windows 10 and Windows 11](https://support.lenovo.com/solutions/HT515094).

### Related Articles

* [How to enable and disable the TouchPad - Windows](https://support.lenovo.com/solutions/ht075599)
* [Video] [Touchpad: Enable/Disable in Windows 11](https://www.youtube.com/watch?v=Y-LmLpfVZj0)
* [Video] [How To – Precision Touchpad Settings in Windows 10](https://www.youtube.com/watch?v=vKT_lfudIqU)
* [Video] [How To – Touchpad Settings in Windows 10, 8, 7 (ThinkPad)](https://www.youtube.com/watch?v=qFNaIb-HxEw)
* [Video] [How To – Touchpad Settings in Windows 10, 8, 7 (Non-ThinkPad)](https://www.youtube.com/watch?v=Cw0p-U9TT1c)
* [Video] [How to enable or disable your Touchpad](https://www.youtube.com/watch?v=2dAJifd7B5w)
* [Fix touchpad problems in Windows](https://support.microsoft.com/windows/fix-touchpad-problems-in-windows-30b498e5-0caa-9740-2b21-336ea75ee756)
* [How to disable TrackPoint - ThinkPad](https://support.lenovo.com/solutions/HT117094)
* [TouchPad auto zoom in and out - ThinkPad](https://support.lenovo.com/solutions/HT117604)
* [TouchPad or TrackPoint response very slow - ThinkPad](https://support.lenovo.com/solutions/HT117605)
* [How to enable touchpad virtual scrolling (Mouse wheel) on ThinkPad](https://support.lenovo.com/solutions/HT503491)
