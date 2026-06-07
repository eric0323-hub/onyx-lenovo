### Symptom

After the system resumes from hibernation mode, Wi-Fi does not work. The machine has to be restarted to resolve the issue.

**Note:** For related issues, see [Fix network connection issues in Windows 10, 11](https://support.microsoft.com/help/10741) or [Frequent drops or intermittent wireless connection](https://support.lenovo.com/solutions/ht502846).

### Applicable Brands

* ideapad
* ThinkPad

### Operating Systems

* Windows 10
* Windows 11

### Solution

#### If your product and WLAN Adapter are: **ThinkPad** with **Intel Dual Band Wireless-AC 8265**

Try to update [Intel 8265 Wireless LAN Driver for Windows 10 & 11 (Version 1709 or later) - ThinkPad](https://support.lenovo.com/downloads/DS502302) (carefully read the Supported System in driver page) to resolve the issue.

For all other products, try following solutions:

#### Method One - Check drivers

1. Make sure the latest WLAN drivers are installed.
2. Open [Device Manager](http://support.lenovo.com/solutions/HT117792).  
   ![Search for Device Manager](https://download.lenovo.com/km/media/images/HT069613/Windows11Devicemansearch_20260311123630866.png)
3. Click the arrow mark beside **Network Adapters** in **Device Manager** dialog box.
4. Locate the WLAN Adapter.  
   **Note:** There is no one name for the Wi-Fi card, so you will have to go through the list and look for something with "wireless," "802.11," or "WiFi" in the name.
5. Double-click the WLAN adapter.
6. Click the **Power Management** tab in the Properties window.
7. Uncheck the **Allow the computer to turn off this device to save power** box.
8. Click **OK**.


#### Method Two - Check Power Options

1. Go to Control Panel to open Power Options.  
   ![Control Panel](https://download.lenovo.com/km/media/images/HT069613/control_20221128154001675.png)
   * Windows 11: Search to open **Control Panel** and go to **System and Security** -> **Power Options**.
   * Windows 10: Search to open **Control Panel** and view by Category, select **System and Security** -> **Power Options**.
2. Next to the currently selected power plan, click **Change plan settings**.
3. Click **Change advanced power settings**.
4. Click to expand the **Wireless Adapter Settings** section, and then click to expand the **Power Saving Mode** section.
5. If the setting is currently anything other than Maximum Performance, click the setting and then select **Maximum Performance**, and then click **Apply**.


#### Method Three - Disable and enable the device

Disable and re-enable the wireless network card in Device Manager.

1. Press the Windows key + X.
2. Select **Device Manager**.
3. Expand the **Network adapters** section.  
   ![Network adapters](https://download.lenovo.com/km/media/images/HT069613/na_20200807113052275.png)
4. Right-click the Wireless network device and select **Disable device**.
5. Right-click the Wireless network device and select **Enable device**.


#### Method Four - Update drivers

Updates are also available with the automatic scan option:

1. Go to <https://support.lenovo.com>.
2. Select **Detect Product**.  
   ![Detect Product](https://download.lenovo.com/km/media/images/HT069613/detectproduct2024_20240805133453409.png)
3. Select **Drivers & Software**.  
   ![Drivers and Software](https://download.lenovo.com/km/media/images/HT069613/driversandsoftware2024_20241106162917856.png)
4. Select **Scan Now** under **Automatic Update** and scan for updates.  
   ![Scan Now](https://download.lenovo.com/km/media/images/HT069613/automaticdriverupdateJan2023_2023112118053850.png)

### Related Articles

* [Popular Topics: Tips for PC's](https://support.lenovo.com/solutions/ht503909)
* [Popular Topics: Windows 11, 10](https://support.lenovo.com/solutions/ht118590)
