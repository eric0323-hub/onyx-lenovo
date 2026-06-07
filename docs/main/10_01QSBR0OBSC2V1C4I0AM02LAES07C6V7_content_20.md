![Battery recall](https://download.lenovo.com/km/media/images/HT080185/battthinkpad.gif)[Is my battery affected by a recall?](https://support.lenovo.com/solutions/ht004883 "Is my battery affected by a recall?")

#### General Battery Troubleshooting steps

1. If the PC has a removable battery, check that the battery is properly attached.
2. Verify that the AC power adapter is correct for the system (check the user manual, [How to find and view manuals for Lenovo products - ThinkPad, ThinkCentre, ideapad, ideacentre](https://support.lenovo.com/solutions/HT077589)).
3. Plug the AC power adapter into the computer and a power outlet (wall outlet). If the laptop has an AC power indicator light, make sure the light comes on. Try a different wall outlet if that does not work. Do not use a power bar.
4. Check the battery health in Lenovo Vantage or Windows.  
   ![Battery settings](https://download.lenovo.com/km/media/images/HT080185/batterysetting_20250717175432997.png)
5. Check to see if the battery can charge, if the battery is below 50%. Some batteries will not charge until they are below a certain level of charge.
6. Update drivers. Updates are available with the automatic scan option:
   1. Go to <https://pcsupport.lenovo.com>.
   2. Select **Detect Product**.  
      ![Find product](https://download.lenovo.com/km/media/images/HT080185/pcsupport_20250717175519661.png)
   3. Select **Drivers & Software**.  
      ![Drivers and Software](https://download.lenovo.com/km/media/images/HT080185/driversandsoftware2024_20250717175558735.png)
   4. Select **Scan Now** under **Automatic Update** and scan for updates.  
      ![Scan Now for Automatic Update](https://download.lenovo.com/km/media/images/HT080185/automaticdriverupdateJan2023_20250717175640205.png)  
      **Note:** Updating your BIOS, drivers, operating system, and applications is critical to make sure you get the most life from your battery.
7. If the battery will not charge, check the age of the battery. Batteries wear out with time and may need to be replaced. See [Battery Q&A](https://support.lenovo.com/solutions/HT509084) for more information.
8. If the battery has recently been replaced, try a hard reset (close applications, shut down the computer, remove power, wait 30 seconds or so, attach power, then power the system back on).
9. If the battery still does not work, contact support at <https://support.lenovo.com/contactnow>.


#### Battery does not charge

Check the following:

1. **Symptom:** The battery cannot be fully charged using the power-off method in the standard charge time for your computer.  
   **Solution**: The battery might be over-discharged. Do the following:  
   
   - Turn off the computer.  
   
   - Make sure that the over-discharged battery is in the computer.  
   
   - Connect the AC adapter to the computer and let it charge.  
   
   - If the optional Quick Charger is available, use it to charge the over-discharged battery.  
   
   - If the battery cannot be fully charged in 24 hours, use a new battery.
2. **Symptom:** Your computer shuts down before the battery status indicator shows empty, -or- Your computer operates after the battery status indicator shows empty.  
   **Solution**: Discharge and recharge the battery.
3. **Symptom:** The operating time for a fully charged battery is short.  
   **Solution**: Discharge and recharge the battery. If your battery's operating time is still short, use a new battery. **Note**: Intensive applications may drain the battery faster than expected.
4. **Symptom:** The computer does not operate with a fully charged battery.  
   **Solution**: The surge protector in the battery might be active. Turn off the computer for one minute to reset the protector; then turn on the computer again.
5. **Symptom:** The battery cannot be charged.  
   **Solution**: The battery cannot be charged when it is too hot. If the battery feels hot, remove it from the computer and allow it to cool to room temperature. If the battery can't be removed, allow the system to cool to room temperature. After it cools, reinstall the battery (if it was removed) and recharge the battery. If it still cannot be charged, contact [support](https://pcsupport.lenovo.com/).
6. **Symptom:** Battery not detected error. Contact [support](https://pcsupport.lenovo.com/).

If your system can only be charged to 55-60%, it may due to conservation mode or the custom battery charge threshold may be turned on. For more information, see [Battery not charging, stops at 60% - Windows - ideapad](https://support.lenovo.com/solutions/ht103159).



#### Battery life (capacity) decreases with age and usage of battery

Capacity is the length of time you can run your system on a fully charged battery. It is normal for all batteries to lose some capacity over time. Each time you discharge and recharge your battery, you will lose a very small amount of this capacity.

You may also want to check for specific information on your system; for example, some BIOS updates include power management enhancements. Other systems have specific tools to help with battery life. To find drivers and files for your system, go to ThinkPad [software and device drive file matrix](https://support.lenovo.com/products?tabName=Downloads) and select the link for your system.

**Note:** Updating BIOS, drivers, operating system, and applications is critical to make sure you get the most life from your battery.



#### Battery discharges when system is unplugged and powered off

The battery will lose capacity when left in a system without the AC power attached because the system will draw a small amount of current that will deplete the capacity over time. Batteries will lose some charge over time due to self discharge; this is normal.

You can check to see which applications are using your battery the most:

**Windows 10**

1. Search for **See which apps are affecting your battery life**.  
   **![Search option](https://download.lenovo.com/km/media/images/HT080185/batteryapps1_20210616131046603.png)**
2. View the list to see the applications.  
   **![Check apps](https://download.lenovo.com/km/media/images/HT080185/batteryapps_20210616131139939.png)**

**Windows 11**

1. Select **Start** and **Settings**.  
   ![Settings](https://download.lenovo.com/km/media/images/HT080185/startsettingsWin11_20250203152250398.png)
2. Go to**System**, **Power & battery**, **Battery Usage**.  
   ![Battery usage](https://download.lenovo.com/km/media/images/HT080185/微信图片_20240704103959_20240704024015329.png)
3. View **Battery usage per app**.   
   ![App usage](https://download.lenovo.com/km/media/images/HT080185/微信图片_20240704104141_20240704024149667.png)

You can also get an energy report.

1. Right-click Windows Powershell and select **Run as Administrator**.  
   ![Powershell](https://download.lenovo.com/km/media/images/HT080185/powershell2_20210616133328614.png)
2. Type the command **powercfg -ENERGY**. This provides a report and lists problems that prevent the laptop from going to sleep. The file can be viewed in a web browser.  
   ![Report](https://download.lenovo.com/km/media/images/HT080185/energyreport_2021061613355093.png)

Additionally, from the PowerShell or Command Prompt, use the **powercfg /batteryreport** command to generate a battery report. Follow the output path to find battery-report.html, which can be viewed in a web browser.



#### System shuts down before, or operates after battery status indicator shows empty

When the actual battery capacity is different from the displayed capacity, the above symptoms can occur. To reset the displayed capacity so it matches the actual capacity, discharge the battery to 10% or below and recharge the battery to at least 96%.



#### System does not operate though the battery is fully charged

Verify system runs on AC power. If so, check battery health in Power Manager as outlined above. If system does not run on AC power, remove battery (if system has removable battery) and retest. If system works, contact support to replace battery. If system still does not operate, contact [Lenovo local technical support center](https://support.lenovo.com/supportphonelist).


### Related Articles

* [Popular Topics: Battery, Power, Boot](https://support.lenovo.com/solutions/ht063051)
* [How to adjust power and sleep settings in Windows](https://support.microsoft.com/windows/how-to-adjust-power-and-sleep-settings-in-windows-26f623b5-4fcc-4194-863d-b824e5ea7679)
* [Windows Support Center](https://support.lenovo.com/solutions/ht512575)
