# **Charging Issues (Not Charging)**

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Lenovo_Logo_20250429174901A001.png)
# Overview

.Charging issues can be complicated but fear not! Charging issues usually are related to software issues or simply a bad port or AC adapter. Good troubleshooting will save you on making the session when it comes to how to best address the issue. And yes, sometimes asking if it is plugged in is a great first step.

# Scope Determination

No charging issues are within Premier Support scope.

# Helpful Links

* [Lenovo Laptop Battery Not Charging, Try these Fixes](https://www.lenovo.com/us/en/glossary/laptop-is-not-charging/?orgRef=https%253A%252F%252Fwww.google.com%252F&srsltid=AfmBOoqZo7M2lSyR3pIji6COSKpFB7O7H9CXw60NVgZCK4vnipIAOjCi)

# Questions Lenovo Agents should be asking

* What is the wattage of the charger you are using?
* Is the charger that came with the machine being used?

# **Troubleshooting**

## General Troubleshooting (Laptop)

* **IMPORTANT !!!** -> If the device has **NO POWER** = use this guide instead ->>>> [No Power issues](https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44eaff0e&title=no+power&back=/homePage/searchDetail)
* **NOTE** -> Some older laptops may have USB-C ports that do not support charging. Confirm the port they are connecting to supports charging via [PSREF](https://psref.lenovo.com/) and [Hardware Maintenance Manual (HHM)](https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-x-series-laptops/thinkpad-x1-carbon-8th-gen-type-20u9-20ua/20u9/20u9005mus/pf3c97et/solutions/ht077589-how-to-find-and-view-manuals-for-lenovo-products-thinkpad-thinkcentre-ideapad-ideacentre)

### **1) AC Adapter check**

1. Confirm that the AC Adapter is correct for the device (65W chargers will not charge 230W machines ect)
2. Confirm customer is using not using a power strip but is plugged directly into the wall
3. (**IF POSSIBLE**) - Have the user use another known working charger **=>** if the other charger works **=>** **send AC Adapter ( no system board)**

### **2) Check the charging port lights ( DO NOT SKIP THIS STEP!!!!)**

1. Plug the charger into the port
2. Check for the LED indicator for a light next to port
   
   * **NOTE**: Most computers that have Type USB-C chargers have two ports that can be used for charging the computer.

Make sure to check ALL charging ports for lights when plugged in**.**

1. Meaning of Light Colors
   
   | Color | Meaning |
   | --- | --- |
   | Red | Critically Low Battery |
   | Amber | Charging |
   | White | Above 90% Charge |
   | NO LIGHT | Charger not detected / port not working |
2. Charging light seen?
   
   * **Yes** = Continue troubleshooting start at “**Conduct system board reset**”
   * **No** = Continue troubleshooting start at “**Conduct system board reset**”

### **3) Conduct system board reset** **(****NOTE****: Model of device will determine method below to use)**

**A) Pin Hole Reset =** [**Instructions (if needed)**](https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44eaffbc&title=pin+hole+reset&back=/homePage/searchDetail)

Issue resolved? (check for charging lights!!! )

**Yes** = **Solution Provided.**

**No** = Continue troubleshooting starting at “**Remote into the machine**”

**B) NOVO button reset =** [**Instructions (if needed)**](https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44ed03fc&title=novo+button&back=/homePage/searchDetail)

Issue resolved? (check for charging lights!)

**Yes** = **Solution Provided.**

**No** = Continue troubleshooting starting at **“Remote into machine”**

**C) Device has neither option above**

* Continue troubleshooting starting at “**Remote into the machine**”

### **4) Remote into the machine**

1. Lenovo Agent should remote into the machine using remote desktop software to conduct software/setting troubleshooting

### **5) Check Lenovo Vantage Settings**

1. Check to see if the Charging Threshold Settings are set
   
   * **NOTE** -> On ThinkBooks the Charge Threshold is set to stop charging at 60% and is not user configurable.
   * **NOTE**-> On ThinkPads the Charge Threshold is user configurable. Default is 80%
2. ![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Picture4_20250429175053A021.png)
3. Turn off for testing purposes
4. Confirm the wattage of the AC Adapter as well
5. ![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Picture3_20250429175054A022.png)

### **6) Check for Airplane Mode**

1. Keyboard
   
   * Some keyboards have this function as a hotkey. Make sure that is not "lit"
   2. Windows 11
   * **Method 1**: Select the Network, volume, or battery icon on the taskbar, then ensure the Airplane mode button is **not highlighted**.
   * **Method 2**: Select **Start** > **Settings** > **Network & internet**  > **Airplane mode**, then ensure the toggle is **Off**.
   3. Windows 10
   * **Method 1**: Select the Network  icon on the taskbar, then select Airplane mode.
   * **Method 2:** Select Start  > Settings  > Network & Internet  > Airplane mode, then select the first toggle for On or Off
   4. Vantage
   * **Device Settings** -> **Power** -> **Power Settings** -> **Airplane Power Mode** -> ensure this is not selected and the small "**auto-detection**" box is **not checked**
2. ![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/ApplicationFrameHost_3pRTl47W0h_20250429175054A022.png)

### **7) Driver check**

1. Drivers vary among different models. The list below is a list of the most COMMON drivers/firmware related to charging

* BIOS
* Lenovo Power and Battery Driver
* Lenovo Power Management Driver (aka Lenovo PM Device)
* I/O drivers
* Thunderbolt 3 or Thunderbolt 4 driver/software driver and/or firmware  
  
  
  2. If drivers are correct and match the drivers listed on the Lenovo Support site for the device → continue to “**Check for charging indicator…**.”
  
  If drivers are incorrect = uninstall / restart / reinstall

### **8) Check for charging indicator on battery icon ( do this for each charging port )**

1. Confirm if the icon shows up
   
   * Windows 10

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Battery_charge_win10_20250429175054A023.jpg)

* Windows 11

* ![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Battery_charge_win11_20250429175054A023.jpg)
  2. Icon Shows?
     
     **Yes** -> check the other port ( if applicable) & if both ports work & you confirm the battery percentage changes -> **Solution Provided**
     
     **No** -> check the other port (if applicable) then go to **Step 9**

### **9) Have the customer check for charging port damage, and provide photos as needed**

1. This step is important as not all machines have ADP and it is important to verify the charging issue is not caused by CID.

### **10) HW Solution**

1. If none of the troubleshooting above has restored the device charging or you have verified 1 port is not charging. => replace sys board
   
   * **IMPORTANT:** Some models have the slim tip charger! These models will have a **DC-IN PORT**. This often is the only part that needs to be sent as it relates to the device not charging. If you can't find DC-in cable, the unit may have it built into the C FRAME. As recently as JUN 2025, some slim-tip devices now have the DC-In Port on the sys board.

  


# General Troubleshooting ( Desktop / Workstation / Towers)

1. Desktops **do not** have batteries so they **do not** "charge"
2. See this link for NO POWER issues with Desktops / Workstations / Towers -> [No Power issues #General Troubleshooting ( Desktops / Towers / Workstations )](https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44eaff0e&title=no+power+issues&back=/homePage/searchDetail)

  


# **Other Charging Related Issues**

# 

## **Laptop powers off when disconnected from AC**

1. If the laptop powers off when the AC is disconnected but the battery is seen by the OS it is likely a corrupted/dead battery regardless of the battery percentage reported. Only if the system board was recently changed would you look at replacing the system board first.
2. **Refer to this guide** => [[[Battery Issues](https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44eafa7a&title=battery+issues&back=/homePage/searchDetail)]]

  


## **Device will not charge if connected at 95% or higher. Confirm this in the system's User Guide.**

1. Verify in the system user guide the following note to see if the unit has software preventing this in the battery.
2. If the user is having this happen tell them to drain to under 5% then plug the machine in and it will charge to 100%.

  


![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Battery_Life_20250429175054A024.png)

  


## **Docking Station is not charging the Laptop**

1. See this guide -> [Dock TS Guide](https://ukm.lenovo.com/#/homePage/homeDetail?uid=0x44edc99c&title=dock+issues&back=/homePage/searchDetail)

  


## **FAQS**

#### Customer is traveling overseas. Which charger do they need?

* https://smartsupport.lenovo.com/om/en/accessories/acc500160

  


## **Known Issues**

### Multi-System

* [https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-x-series-laptops/thinkpad-x1-carbon-9th-gen-type-20xw-20xx/solutions/ht513369-thinkpad-usb-c-port-charging-issues-x1-carbon-9th-gen-x1-yoga-6th-gen-and-x1-nano-gen-1 Critical BIOS Update for USB-C Port Charging - ThinkPad] (Resolved)
* Lenovo has released Critical BIOS updates for select ThinkPad systems to prevent charging issues with some USB-C power device configurations. Multiple ThinkPad systems
* [https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-edge-laptops/thinkpad-e15-gen-2-type-20td-20te/20td/20td00j5us/pf3r44nb/solutions/ht514028 Critical BIOS and PDFW Update for USB-C Port Charging - ThinkPad E14 Gen 2 and ThinkPad E15 Gen2] (resolved)\*\*Lenovo has released Critical BIOS and PDFW updates for ThinkPad E14 Gen 2 and ThinkPad E15 Gen 2 to prevent charging issues with some USB-C power device configurations.

  


### Machine Specific

#### E14/E15 Gen 1 + Gen 2

**Issue** -> Device won't charge   
**Solution** -> https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-edge-laptops/thinkpad-e15-gen-2-type-20td-20te/20td/20tds00b00/mj0gs5pj/solutions/ht515083-eca-0476-not-chargingno-power-thinkpad-e14-e15-gen-2   


#### X1 Carbon Gen 9 / X1 Yoga Gen 6

**Issue** -> Device won't charge   
**Solution** -> https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-x-series-laptops/thinkpad-x1-carbon-9th-gen-type-20xw-20xx/20xx/20xxs2g900/pf3mk2ql/solutions/ht515289-eca-0480-not-chargingno-power-thinkpad-x1-carbon-gen-9-x1-yoga-gen-6

Lenovo Confidential | Generated on 2025-04-01 22:07
