# 📋 Battery Issues Overview

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Lenovo_Logo_20250429174901A001.png)
## 🔄 Scope Determination

Batteries are included in our support scope, but assistance is contingent upon the warranty level of the machine.

We can assist customers experiencing battery issues; however, whether we can send a replacement battery to resolve the issue depends on the warranty status.

## ⚙️ Understanding Battery Life

Battery life is a common concern for our customers. It is essential to note that battery life is not easily quantifiable and is influenced by several factors:

1. **Display Operation**: Brightness level and resolution (e.g., High Definition, 4K)
2. **Processor**: The type of processor in the device
3. **Power Settings**: Selected power mode (e.g., High Performance, Balanced)
4. **User Usage**: Individual usage patterns

Avoid making blanket statements regarding battery life expectations, as these factors can vary significantly between users.

## 🔍 Helpful Links and Questions for TSS

When addressing battery issues, TSSs should consider the following questions:

* When did the issue start?
* Does the machine power off when unplugged?
* Is there a red X over the battery icon?
* Are there any warning messages regarding the battery?
* Have you checked both USB-C ports to confirm they charge the device?
* What is the wattage of the AC Adapter being used?

**Note**: The battery may discharge when the system is powered off or in a sleep state, particularly for ThinkPad and ideapad models.<https://support.lenovo.com/solutions/HT509457>

## Troubleshooting

### General Guidelines (Determine if the Battery is the problem and not the sys board and /or charging)

* **GUIDELINE 1** - if the device will not stay powered on without the AC Adapter attached, this is a **STRONG** indicator that there is a battery issue.
* **GUIDELINE 2** - X over the battery icon, this is a STRONG indicator that there is a battery issue

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/No-battery-is-detected_20250429175001A008.png)

* **GUIDELINE 3** - Hardware error window that looks like the picture below is a STRONG indicator that there is a battery issue

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Battery-Not-Detected_20250429175001A008.jpg)

**GUIDELINE 4 -** Battery report is showing strange readings

![](https://ukm.lenovo.com/prod-api/file/download?key=accessory/a521f99627864b59b7b12b3d51534bfd-1750840111574.jpg&name=Battery_Big_Flux_In_capacity_report..jpg)

Big fluctuation in capacity / Note the "millions" of watt hours

![](https://ukm.lenovo.com/prod-api/file/download?key=accessory/1d05eaeee41b473fae77fead9ec4389c-1750840124073.jpg&name=Battery_Big_Flux_In_reported_hours_battery_is_running..jpg)

Big change in the Usage History / note the couple million of hours reported

![](https://ukm.lenovo.com/prod-api/file/download?key=accessory/254b5ff988604664a65003c60bbe20f3-1750840134553.jpg&name=Battery_Negative_mWh..jpg)

Negative capacity being reported

![](https://ukm.lenovo.com/prod-api/file/download?key=accessory/d1f036d7afe142f585296c117804b8a4-1750840146395.jpg&name=Battery_Strange_Battery_Capacity..jpg)

Very low watt / unexplained hours in capacity history that doesn't match Design / Full Charge capacity at the top of the battery report.

![](https://ukm.lenovo.com/prod-api/file/download?key=accessory/63295460f21a4b2d9768ae00578f7dfc-1750840163131.jpg&name=Battery_Heavy-Drain_High_Cycle_Count..jpg)

Much lower number for "FULL CHARGE CAPACITY" when compared to the DESIGN CAPACITY and very high cycle count.

![](https://ukm.lenovo.com/prod-api/file/download?key=accessory/c3c5bdc4b0df4da099bf1966bb9a6cbc-1750840172080.jpg&name=Battery_Huge_Dips_in_battery_drain_consistantly..jpg)

Major battery drain in a short amount of time. The bottom graph shows the battery percentage going from 100% to 2 % rapidly. NOTE - Its important to note the activity CX was doing and the timestamps to see if this is normal activity or very strange.

# General Troubleshooting: Confirming Battery Issues 🧰

## 🧰 Run Battery Diagnostics (if needed)

1. **Power off the machine.**
2. **Boot into Lenovo Diagnostics:**
   
   * Press the **F10** button during startup.
   * **Note:** If the device does not allow access to the F10 menu, hold the **SHIFT** key and restart the machine from the **START** menu, then try again.
3. **Select "Battery Diagnostics."**
   
   * This will initiate a battery test.

### Check Results

* **No Failures:** Conduct further troubleshooting if not already done.
  
  + ⚠️ **Warning:** See note below regarding troubleshooting.
  + **Note:** Some diagnostic versions may display a battery lifespan test warning. This does not indicate a bad battery but rather that the battery life is degraded. Confirm this with a battery report. All batteries degrade over time; this warning alone is insufficient for battery replacement.[WARNING result with Battery Quick Diagnostic test - ThinkPad - Lenovo Support US](https://pcsupport.lenovo.com/us/en/solutions/ht511752)
* **Failure:** If the battery health fails, replace the battery.
  
  + **Note:** Confirm if you can send a replacement battery before promising the customer anything by referring to the "Can I send a battery?" section below.

## 💻 Remote into the Machine

1. **Confirm Battery Status:**
   
   * Check if the battery icon is present in the tray on the bottom right side.
   * If the icon exists and displays a lightning bolt (Windows 11) or wall plug (Windows 10), follow the guide for <https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44f41438&title=System+Not+Charging>
   * If a red X or an X over the battery is present, document this and proceed to the next step.
2. **Collect a Battery Report:**
   
   * Click the **Windows Search** icon.
   * Type **"Cmd"** and right-click the icon to select **"Run as administrator."**
   * Enter the following command:
     
     ```
     powercfg /batteryreport
     
     ```
   * Press **Enter**.
   * Enter the next command:
     
     ```
     battery-report.html
     
     ```
   * This will open a browser to view the report. Save the webpage or note the path where it is stored for your records.
   * **How to read the battery report:** [CLICK HERE](https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44f02c0a&title=How+to+read+the+battery+report)

## ⚙️ Driver Check

1. **Lenovo PM Device:**
   
   * Navigate to **Device Manager** > **System devices** and confirm the driver version.
   * If needed, uninstall, restart, and reinstall the driver.
2. **Lenovo Power and Battery:**
   
   * Navigate to **Device Manager** > **System devices** and confirm the driver version.
   * If needed, uninstall, restart, and reinstall the driver.

## 🔄 Pin Hole Reset

* [CLICK HERE IF NEEDED FOR STEPS](https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44f44f6a&title=Pin+Hole+Reset)

## Confirm Issue

Check for the following conditions:

* Battery not detected (X on battery icon)
* Device cannot run without AC adapter
* Lenovo Hardware warning window still appears

### If Yes (Y):

* Ensure the device is charging.
  
  + **Note:** USB-C type AC adapters can charge in both USB-C ports. Check both ports.

### If No (N):

* Replace the battery.
  
  + **Note:** Confirm if you can send a replacement battery before promising the customer anything by referring to the "Can I send a battery?" section below.

## Device Won't Power On Due to Battery (per Customer)

It is extremely rare for the battery to be the source of this problem. Please follow this guide for this reported issue: [**No Power Issues**](http://10.37.162.121/Premier/Wiki/index.php/No_Power_issues) [**https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44f469d2&title=No+Power+Issues+**](https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44f469d2&title=No+Power+Issues+&back=/homePage/searchDetail&searchId=ho72ik0vomdchsnqv)

## Device / Battery Won't Charge

If the device is not charging, refer to this guide: [**System Not Charging**](http://10.37.162.121/Premier/Wiki/index.php/System_Not_Charging)

[**https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44f41438&title=System+Not+Charging**](https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44f41438&title=System+Not+Charging&back=/homePage/searchDetail&searchId=lnwklhpyxmdchu06r)

## Battery Won't Charge to 100%

### If Device is New or Fresh Out of Box (OOB):

1. Discharge the battery to under 5%.
2. Reconnect the power cable; the device should charge to 100%.

### Issue Fixed?

* **Yes (Y):** Solution Provided.
* **No (N):** Conduct General Battery Troubleshooting (see above).

### If Device Has Been in Use for a While:

1. Reset the system board.
2. Perform a pin hole reset.
   
   * [CLICK HERE FOR STEPS](https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44f469d2&title=No+Power+Issues+)
3. Perform a NOVO button reset (certain models).
4. Check Vantage Threshold setting:
   
   * Open **Lenovo Vantage** / **Lenovo Commercial Vantage**.
   * Click **Device** > **Power**.
   * Scroll down to find **Battery Settings**.
   * Check settings:
     
     + **ON:** Turn this off if the customer doesn't want charging to start/stop at set points.
     + **OFF:** Go to step 3.
5. **Check Drivers:**
   
   * BIOS
   * Lenovo Power and Battery
6. **Drain Battery:**
   
   * Discharge the battery to under 5%.
   * Reconnect the power cable; the device should charge to 100%.

### Issue Fixed?

* **Yes (Y):** Solution Provided.
* **No (N):** Conduct General Battery Troubleshooting (see above).

## Device Has Low Battery Life

**Coming Soon**

## FAQs

### Can I Send a Battery?

Use this guide to determine if the conditions qualify for a battery replacement:

* **No Battery Warranty & Current Date is Past the 1-Year Ship Date:** No
* **Within 1 Year of Ship Date:** Yes
  
  + Confirm with iBASE: [iBASE Login](http://csp.lenovo.com/ibinapp/il/Login.jsp)
* **Unit Has a 3-Year Sealed Battery Warranty:** Yes
* **X1 Carbon Gen 7/8, X1 Yoga Gen 4/5:** Yes
  
  + See [Lenovo Support](https://pcsupport.lenovo.com/us/en/preauth?ReturnUrl=http%3A%2F%2Fpcsupport.lenovo.com%2Fus%2Fen%2Fproducts%2Flaptops-and-netbooks%2Fthinkpad-x-series-laptops%2Fthinkpad-x1-yoga-4th-gen-type-20qf-20qg%2Fsolutions%2Fht510642-battery-icon-may-disappear-x1-carbon-7th-and-yoga-4th).

### Is the Battery Swollen/Bloated?

* **Yes:** Pictures are required before sending the battery!

### CMOS Battery Issues?

* **Yes:** Note that this applies only to the CMOS battery, not the internal or external battery. CMOS batteries are covered for the entire length of the device's active warranty.

### Device Has Premier Plus Warranty?

* **Yes:** Premier Plus includes the battery warranty.

### Important

If we cannot send a battery due to the conditions listed above after determining an issue exists, recommend depot repair (billable) or inform advanced users/IT professionals that they can purchase the battery at [Lenovo Encompass](https://lenovo.encompass.com/) and self-install.

## 🎯 How to Extend Battery Life

For official Lenovo guidance, refer to the following link: [Lenovo Guide](https://support.lenovo.com/us/en/solutions/ht069687).

1. **Reduce LCD Brightness Level:** The display is one of the largest users of battery power. Lowering the brightness can significantly save battery life.
2. **Unplug Unneeded Devices:** Remove devices like phones or headphones that are charging to conserve battery life.
3. **Turn Off Bluetooth:** Disable Bluetooth if not in use to avoid draining the battery.
4. **Shut Down or Hibernate the Laptop:** Instead of using standby, shut down or hibernate the laptop if it won't be used for a while.
5. **Use Power Management Settings:** In Windows, click **Power Options** under Control Panel. For systems preloaded with Battery not charging, it is recommended to select **Optimize for Battery Lifespan** mode or **Conservation Mode** and keep the AC adapter connected.

## 🔍 How to Run and Read a Battery Report

[CLICK HERE TO LEARN MORE](https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44f02c0a&title=How+to+read+the+battery+report)

## Customer Needs to Dispose of a Used Battery. What Can I Recommend?

Direct the customer to this link: [Battery Disposal Information](https://www.lenovo.com/us/en/social_responsibility/sustainability/ptb_us/)

## Known Issues

#### Multi System Types

[Ideapad Line -> Won't charge past 60%](https://support.lenovo.com/us/en/solutions/ht103159)

  
Thinkpad Line   


* [Defective Manufactory Battery (Certain batteries only)](https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-x-series-laptops/thinkpad-x1-carbon-9th-gen-type-20xw-20xx/solutions/ht512607)

* [Battery may discharge when system is powered off or in a sleep state](https://support.lenovo.com/us/en/solutions/ht509457)

#### Machine Specific .

[Thinkpad X1 Carbon Gen 7/8 and X1 Yoga Gen 4/5 -> Defective Battery](https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-x-series-laptops/thinkpad-x1-yoga-4th-gen-type-20qf-20qg/solutions/ht510642-battery-icon-may-disappear-x1-carbon-7th-and-yoga-4th)
