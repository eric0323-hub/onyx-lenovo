# System Not Charging 🧰

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Lenovo_Logo_20250429174901A001.png)
## SYMPTOM

The customer’s laptop is not charging, whether connected to a dock or not.

## APPLICABLE BRANDS

All Think laptops

## SOLUTION

### Physical Troubleshooting Steps

1. **Perform a Power Hardware Reset (PHR)** to reset the power system.
2. **Connect the AC Adapter**:
   
   * Use the AC adapter that shipped with the laptop.
   * Confirm the wattage of the adapter via the emboss on the AC adapter.
   * Connect directly to a wall outlet, bypassing any surge protectors or power strips.
3. **Test USB-C Ports**: For systems with multiple USB-C ports capable of charging the battery (check the User Guide), test each port.
4. **Check Power LED**: Look for the power LED next to the AC input on the laptop.
5. **Power Button Light**: Confirm that the power button light blinks when connecting the AC adapter.
6. **Test Another AC Adapter**: If there are no lights when connecting the AC adapter, check another AC adapter if possible.
7. **Inspect Charging Port**: Have the customer check for any damage to the charging port and provide photos as needed.

### Laptop Powers Off When Disconnected from AC

If the laptop powers off when the AC is disconnected but the battery is recognized by the operating system, it is likely a corrupted or dead battery, regardless of the battery percentage reported. Only if the system board was recently changed should you consider replacing the system board first.

* **Potential Hardware Causes**:
  
  + Battery
  + System board
  + DC-in
  + AC adapter
* **Additional Notes**:
  
  + If the system has a DC-in, always send that with the system board.
  + The DC-in may be part of a c-cover or frame on P workstation laptops.
  + Batteries are not covered by the Premier warranty.
  + The Premier Plus warranty includes a 3-year sealed battery warranty.
  + Batteries have a 1-year factory warranty, even if not listed, and an optional sealed battery warranty that starts after the 1-year period.

## Software Troubleshooting/Information Gathering 💻

* Always update firmware if possible, as a low battery charge may block some updates and power drivers.
* Check the tips for the system for any documented charging or battery issues.
* Remember to be logged in to see Servicer Tips.

## Many of our modern systems will not charge if connected at 95% or higher. Confirm this in the system's User Guide.

* This is user facing and can be shared with the customer.

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Battery_Life_20250429175752A095.png)
## Confirm that Windows sees both the AC adapter connected and the battery by clicking the battery icon in the Task Tray, record the status.

* If battery is not seen you will need to TS that. Primary symptom would be laptop shuts down when disconnected from AC.

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Picture2_20250429175752A095.png)
## In Vantage (install Commercial Vantage if needed) record the wattage of the connected adapter.

* Reporting of a 15w adapter is an indicator of a problem, but the problem can be SW or HW related.
* TB4 Universal Docks docks can provide up to 100w of power independent of what the system shipped with.

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Picture3_20250429175752A096.png)
## In Vantage confirm that a Battery Charge Threshold is not enabled, located under Device>Power

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Picture4_20250429175752A096.png)

* On ThinkPads the Charge Threshold is user configurable. Default is 80%.
* On ThinkBooks the Charge Threshold is set to stop charging at 60% and is not user configurable.

## In Vantage Confirm that Lenovo Vantage Airplane Power Mode is disabled, and Auto detection is disabled

* This is common for AC adapter low wattage errors on boot

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/ApplicationFrameHost_3pRTl47W0h_20250429175752A097.png)
## Confirm in the Windows Control Panel>Power Options that the system is set to Balanced power plan

* This setting may only be available on P series workstations

## In the Windows notification center confirm Airplane Mode is disabled

* While this is primarily radios this has affected charging in the past

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Picture5_20250429175752A097.png)
## Dock Charging Troubleshooting 🧰

1. **Confirm Dock Functionality**
   
   * Use the **OCM** (Onboard Control Module) to verify that the dock can charge the system.
2. **Verify AC Adapter Usage**
   
   * Ensure that the correct **AC adapters** that shipped with the dock are being used.
3. **Check Dock Compatibility**
   
   * For **TB3** and **TB4** docks, confirm that the dock SKU is appropriate for **Workstation class laptops**.
4. **Adapter Specifications**
   
   * For TB3 docks:
     
     + Use a **Y-splitter** with a **230W** or **270W** AC adapter.
     + Older TB3 Workstation docks may have shipped with two AC adapters:
       
       - A **65W** adapter connecting to the lower-right AC port.
       - A **230W** adapter connecting to the top-left AC port.
   * For TB4 docks:
     
     + A **300W** AC adapter is required.
5. **Cable Requirements**
   
   * A **Workstation cable** is necessary to power the laptop.
   * Note that standard **135W docks** will not charge Workstation class laptops.
6. **Inspect Dock Cable Connections**
   
   * Confirm all dock cable connections. If needed, request photos of the configuration for clarity.
7. **Test Adapter on Laptop**
   
   * If using a Workstation class laptop, test the **slim tip adapter** from the dock on the laptop.
8. **Check USB-C Port Compatibility**
   
   * Some older laptops may have USB-C ports that do not support charging. Confirm that the port being used supports charging.
9. **Power Button Indicators**
   
   * The power button on the dock will indicate the following:
     
     + **White**: Computer is on.
     + **Amber**: Dock is on but not connected to a computer.

### Help Tips

* [WARNING result with Battery Quick Diagnostic test - ThinkPad](https://pcsupport.lenovo.com/us/en/solutions/ht511752)
  
  + When executing Lifespan Mode Test of the Battery Quick Diagnostic test in ThinkPad UEFI Diagnostics, a WARNING result may occur.
* [Critical BIOS and PDFW Update for USB-C Port Charging - ThinkPad E14 Gen 2 and ThinkPad E15 Gen2](https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-edge-laptops/thinkpad-e15-gen-2-type-20td-20te/20td/20td00j5us/pf3r44nb/solutions/ht514028)
  
  + Lenovo has released Critical BIOS and PDFW updates for ThinkPad E14 Gen 2 and ThinkPad E15 Gen 2 to prevent charging issues with some USB-C power device configurations.
* [Critical BIOS Update for USB-C Port Charging - ThinkPad](https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-x-series-laptops/thinkpad-x1-carbon-9th-gen-type-20xw-20xx/solutions/ht513369-thinkpad-usb-c-port-charging-issues-x1-carbon-9th-gen-x1-yoga-6th-gen-and-x1-nano-gen-1)
  
  + Lenovo has released Critical BIOS updates for select ThinkPad systems to prevent charging issues with some USB-C power device configurations. Multiple ThinkPad systems
* [Battery not charging when connected to the AC adapter - ThinkPad](https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-x-series-laptops/thinkpad-x1-carbon-9th-gen-type-20xw-20xx/solutions/ht512607)
  
  + The system battery icon may show the system battery is not charging when connected to the AC adapter.
* [Battery icon may disappear - ThinkPad X1 Carbon 7th-8th Gen, X1 Yoga 4th-5th Gen](https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-x-series-laptops/thinkpad-x1-carbon-7th-gen-type-20qd-20qe/solutions/HT510642-BATTERY-ICON-MAY-DISAPPEAR-X1-CARBON-7TH-AND-YOGA-4TH)
  
  + The battery icon may report the ThinkPad battery charge level as invalid (255%)
  + The battery icon may disappear or not show a battery installed
  + The system may unexpectedly hibernate or shutdown when using battery power
