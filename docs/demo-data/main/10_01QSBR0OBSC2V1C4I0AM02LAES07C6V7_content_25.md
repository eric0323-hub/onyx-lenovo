### Symptom

The display is not working.

Use the following steps to resolve display, screen, or monitor issues.

1. [Check Power](#Power)
2. [Check for Logo or BIOS screen](#logo)
3. [Check Cables](#external)
4. [Check the Monitor Settings](#msettings)
5. [Check Display Settings](#display)
6. [Update or Roll Back Drivers](#Update)
7. [Try Different Applications](#different)
8. [Try the following Microsoft links for flickering issues in Windows](#flickering)
9. [Get Support or Warranty Help](#help)

**Note:**

* ThinkStations - Check processor type and see if an onboard video is supported.
* Desktops - If the system has discrete or integrated (onboard) graphics, make sure the video cable is attached to the correct card.

### Operating Systems

* Windows 10
* Windows 11

### Solution

#### Check Power

Make sure the PC has power (sound or lights), see [Troubleshooting No Power Issues](https://support.lenovo.com/solutions/HT510410).

You can also follow these brief steps:

1. Ensure that the power cable is securely plugged into both the PC and the power outlet.
2. Check that the power outlet is working by plugging in a different device, such as a lamp.
3. Look for any lights or indicators on the PC that show it is receiving power. For example, many PCs have a power light on the front panel that turns on when the PC is powered on.
4. Press the power button on the PC to see if it turns on. If nothing happens, try holding down the power button for a few seconds to see if this initiates the power-up process.



#### Check for Logo or BIOS screen

If nothing is displayed on the screen, see if the logo screen or BIOS screen can be displayed.

* [Recommended way to enter BIOS - ideapad](https://support.lenovo.com/solutions/ht500216)
* [Recommended ways to enter BIOS - ThinkPad, ThinkCentre, ThinkStation](https://support.lenovo.com/solutions/ht500222)
* [Recommended way to enter BIOS for Lenovo Desktops & All-In-Ones - Windows](https://support.lenovo.com/solutions/ht500217)

![Logo screen](https://download.lenovo.com/km/media/images/HT510324/1234_20230614031849557.png)

If you can see the BIOS menu, this suggests that there is no problem with your power supply, and there may be a software issue. Once you enter BIOS, use the arrow keys to navigate through the BIOS menu to find the option to reset the computer to its default or factory settings.

**Note**: This will erase all the data, make sure you have a backup.



#### Check cables if using an external monitor

1. Make sure the correct cables are connected from the PC to the monitor. For general information, see [What are the types of monitor connections?](https://www.lenovo.com/us/en/glossary/types-of-monitor-connections/?orgRef=https%253A%252F%252Fwww.google.com%252F) Check your PC manual for more information (check for connectors or HDMI).
2. Make sure the cables are not loose.
3. Make sure the power cable is firmly attached to the monitor.
4. Consider trying a different monitor or cable, if available.
5. Try connecting the monitor to a different PC, if more than one is available.

For more information, see [How to connect to an external monitor - ThinkPad - Windows 10, 11](https://support.lenovo.com/solutions/HT509850).



#### Check the monitor settings

* Make sure that the correct input source is selected on the monitor and that the display resolution and refresh rate are set correctly. See [View display settings in Windows 10 and 11](https://support.microsoft.com/en-us/help/4027860/windows-10-view-display-settings).
* For monitor settings, you'll need the user manual from the monitor manufacturer.


#### Check Display Settings

* For general display issues, check display settings.  
  
  Right-click the desktop, choose **Display settings**, and see options for changing display settings.  
  ![Display settings](https://download.lenovo.com/km/media/images/HT510324/DisplaySettings_20220526153752809.png)
* Try setting the **Display resolution** to the recommended setting.  
  ![Display](https://download.lenovo.com/km/media/images/HT510324/displayrecommended_20230206155104852.png)  
  
  Windows 11:  
  ![Scale & layout](https://download.lenovo.com/km/media/images/HT510324/Windows11resolutionscale_20260109143841310.png)
* Some flickering issues may be resolved by changing the refresh rate.  
  
  Right-click the desktop, select **Display settings**, **Advanced display settings**, **Display adapter properties for Display 1**, and then select the **Monitor** tab. Select a refresh rate that is supported by the monitor.  
  ![Monitor](https://download.lenovo.com/km/media/images/HT510324/monitortab_20221031133529390.png)
* For basic troubleshooting steps, see Troubleshoot screen flickering in Windows 10 and 11.  
  <https://support.lenovo.com/solutions/HT501290>
* View display settings in Windows 10 and 11.  
  <https://support.microsoft.com/en-us/help/4027860/windows-10-view-display-settings>


#### Update or Roll Back Drivers

Updates are also available with the automatic scan option:

1. Go to <https://support.lenovo.com>.
2. Select **Detect Product**.  
   ![Detect Product](https://download.lenovo.com/km/media/images/HT510324/detectproduct2024_20240715173644946.png)
3. Select **Drivers & Software**.  
   ![Drivers and Software](https://download.lenovo.com/km/media/images/HT510324/driversandsoftware2024_20240715173806302.png)
4. Select **Scan Now** under **Automatic Update**.  
   ![Automatic Update](https://download.lenovo.com/km/media/images/HT510324/automaticdriverupdateJan2023_20240222145338349.png)

How to roll back a driver if the issue occurred after a recent update.

1. Find the driver in [Device Manager](https://support.microsoft.com/windows/open-device-manager-a7f2db46-faaf-24f0-8b7b-9e4a6032fc8c) (search for and select **Device Manager**). Expand the display or monitor section.  
   ![Device Manager](https://download.lenovo.com/km/media/images/HT510324/Windows11Devicemansearch_20250710173001410.png)
2. Right-click the driver and select **Properties**.
3. Select the **Driver** tab and select **Roll Back Driver** if the option is available. If Roll Back Driver is grayed out, this means no earlier versions were installed.  
   ![Roll Back Driver](https://download.lenovo.com/km/media/images/HT510324/rollbackdriver_20241021184729129.png)
4. Reboot the PC.


#### Try different applications

If the display issue occurs in a specific application, close the application, and try a different application to see if the issue still occurs. If the issue only occurs in a specific application, try checking any display settings the application might have. Check with the manufacturer of the application for any updates.



#### Try the following Microsoft links for flickering issues in Windows

Try the following Microsoft link for flickering issues in Windows 10:

[Troubleshoot screen flickering in Windows 10](https://support.microsoft.com/en-us/windows/troubleshoot-screen-flickering-in-windows-47d5b0a7-89ea-1321-ec47-dc262675fc7b#WindowsVersion=Windows_10).

Try the following Microsoft link for flickering issues in Windows 11:

[Troubleshoot screen flickering in Windows 11](https://support.microsoft.com/en-us/windows/troubleshoot-screen-flickering-in-windows-47d5b0a7-89ea-1321-ec47-dc262675fc7b#WindowsVersion=Windows_11).



#### Get support or warranty help

You may require a repair if your computer screen can no longer support your normal activity.

Support Availability - [Contact Us](https://pcsupport.lenovo.com/contactus)


### Related Articles

* [Troubleshoot black screen or blank screen errors](https://support.microsoft.com/sbs/windows/troubleshoot-black-screen-or-blank-screen-errors-79bcd941-5c32-5da9-9a99-9ed1a53b0d94)
* [Popular Topics: Screen, display](https://support.lenovo.com/solutions/ht506564)
* [Video] [How To - Laptop Doesn’t Power On - Lenovo Support US](https://support.lenovo.com/videos/vid100760)
