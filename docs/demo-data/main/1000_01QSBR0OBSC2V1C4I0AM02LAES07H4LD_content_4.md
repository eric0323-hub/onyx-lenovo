#### Make sure the touchpad is enabled

Use Keyboard keys

1. Look for the key with this icon on the keyboard. The button may vary depending on models.  
   ![Touchpad key](https://download.lenovo.com/km/media/images/HT515620/ideapad520touchpadkey_20230831181612878.png)
2. The TouchPad will be enabled automatically after a reboot, resuming from hibernation/sleep mode, or entering Windows.
3. Press the corresponding button (such as F6, F8 or Fn+F6/F8/Delete) to disable the touchpad. If the shortcut key does not disable or enable the touchpad, go to [Lenovo support website](http://support.lenovo.com) to download and install the latest touchpad driver, then retry.

Some keyboards may not have a key for the touchpad. Select **Start**, **Settings**, **Devices**, and then **Touchpad** (or search for Touchpad) to change touchpad settings.

Check the User Guide or Manual and search for function keys to see what keys the keyboard has: [How to find and view manuals for Lenovo products - ThinkPad, ThinkCentre, ideapad, ideacentre](https://support.lenovo.com/solutions/HT077589)



#### Install current drivers

**Update Drivers:**

Go to the [Lenovo Support website](http://support.lenovo.com/) and download the newest touchpad driver. For more information, see [How to navigate and download Lenovo software or drivers from Lenovo Support Site](https://support.lenovo.com/solutions/ht117260).

1. Drivers can also be found under **Drivers & Software** on the left side of the Product Home page.  
   ![Drivers and Software](https://download.lenovo.com/km/media/images/HT515620/driversandsoftware2024_20241111133739464.png)
2. Select **Manual Update** or **Automatic Update** to update the drivers.  
   ![Updates](https://download.lenovo.com/km/media/images/HT515620/automaticdriverupdateJan2023_20230905184907690.png)

**Roll Back Drivers:**

If this used to work, consider rolling back the touchpad driver.

1. In the search box on the taskbar, type **device manager**, and then select **Device Manager** in the results.  
   ![Device Manager](https://download.lenovo.com/km/media/images/HT515620/Windows11Devicemansearch_20260310125749990.png)
2. Expand the **Mice and other pointing devices** or **Human Interface Devices** category.
3. Right-click the driver.
4. Select **Properties**.  
   ![Properties](https://download.lenovo.com/km/media/images/HT515620/Mice1_20230905185041896.png)
5. Select **Roll Back Driver** under the **Driver** tab.  
   ![Driver](https://download.lenovo.com/km/media/images/HT515620/rollback2_202309051851449.png)

If the touchpad driver is not visible in Device Manager:

1. Search for and select **Device Manager** (or use Windows key + S to search for Device Manager).  
   ![Device Manager](https://download.lenovo.com/km/media/images/HT515620/Windows11Devicemansearch_20260310125915876.png)
2. Select **View**, then **Show Hidden Devices** (use Alt + V to select the View tab menu, use down arrow to move to the menu option, and Enter to select).
3. Check under **Human Interface Devices** or **Mice and other pointing devices** and see if the touchpad driver is grayed out (use up or down arrows to move up or down the list and left or right arrows to close or expand the sub-list). If so, highlight the driver and use the **Action** tab (alt + A). Click **Update driver** (use Enter to select the menu option).  
   ![Update driver](https://download.lenovo.com/km/media/images/HT515620/update5_20230905185317384.png)
4. After updating the driver, try restarting Windows.

**Reinstall the driver if the previous steps do not work:**

1. In the search box on the taskbar, type device manager, and then select **Device Manager** in the results.
2. In **Device Manager**, expand the **Human Interface Devices** or **Mice and other pointing devices** category. Under this category, right-click the driver. A context menu will pop up. Then select **Uninstall** or **Uninstall device**.  
   ![Uninstall](https://download.lenovo.com/km/media/images/HT515620/uninstallt_20230905185428314.png)
3. Restart the PC for the change to take effect. After restarting, Windows will attempt to reinstall the driver.


#### Run keyboard troubleshooter

1. Go to **Start**, **Settings**.
2. Select **Update & Security**, **Troubleshoot**, **Other troubleshooters (**or **Additional troubleshooters)**.
3. Run the keyboard troubleshooter.  
   
   ​For details, see [How to run Windows Troubleshooters - Windows 10 and Windows 11](https://support.lenovo.com/solutions/HT515094).


#### Check the touchpad sensitivity

Check the touchpad settings in Windows to adjust sensitivity. For details, see [Video] [Touchpad Settings in Windows 10, 8, 7 - Lenovo, IdeaPad](https://support.lenovo.com/videos/VID500010).

1. Search for and select **touchpad settings**.  
   ![Touchpad settings](https://download.lenovo.com/km/media/images/HT515620/Touchpadsearch_20230906180651610.png)
2. Adjust the sensitivity.  
   ![Touchpad sensitivity](https://download.lenovo.com/km/media/images/HT515620/touchpadsen_20230906183357561.png)  
   ![Touchpad sensitivity](https://download.lenovo.com/km/media/images/HT515620/Windows11touchpadsensitivity2026_2026031013123798.png)


#### Check the touchpad in Safe mode

Reboot the computer and enter Safe mode to see if the touchpad works normally.

See the following links for more information:

* [How to enter safe mode in Windows 10](https://support.lenovo.com/solutions/ht105328)
* [Start your PC in safe mode in Windows 10](https://support.microsoft.com/windows/start-your-pc-in-safe-mode-in-windows-10-92c27cff-db89-8644-1ce4-b3e5e56fe234)
* [Start your PC in safe mode in Windows](https://support.microsoft.com/en-us/windows/start-your-pc-in-safe-mode-in-windows-92c27cff-db89-8644-1ce4-b3e5e56fe234#WindowsVersion=Windows_11)

If the touchpad works in Safe mode, then the issue may be with a specific application or driver. If the issue is with the application, check to see if there is an update for the application.



#### Set BIOS to default settings

Press F2 or Fn and F2 (some products use F1 or Fn and F1) after powering on the computer to enter the BIOS (before the Windows desktop is visible). Then press F9 or Fn and F9 and select **Load Default Settings**.

* [Recommended way to enter BIOS for Think Series](https://support.lenovo.com/solutions/HT500222)
* [Recommended way to enter BIOS for IdeaPad, Lenovo Laptops](https://support.lenovo.com/solutions/HT500216)
* [Recommended way to enter BIOS for Lenovo Desktops and All-in-Ones](https://support.lenovo.com/solutions/HT500217)

Turn the computer off and then back on and see if the touchpad works.



#### Restore Point

If the issue occurred after a recent update, using a restore point may help.

For more information, see:

[Restore from a system restore point](https://support.microsoft.com/en-us/windows/recovery-options-in-windows-31ce2444-7de3-818c-d626-e3b5a3024da5#bkmk_restore_from_system_restore_point) Scroll down to the information about **Restore from a system restore point**.


### Related Articles

* [Popular Topics: Tips for PC's](https://support.lenovo.com/solutions/ht503909)
* [How to enable and disable the TouchPad - Windows - ideapad](https://support.lenovo.com/solutions/HT075464)
* [Touchpad or trackpad is not working - ThinkPad](https://support.lenovo.com/solutions/HT104456)
* [Video] [Touchpad Response is Very Slow in Windows 10 (Idea, Lenovo)](https://support.lenovo.com/videos/vid500013)
