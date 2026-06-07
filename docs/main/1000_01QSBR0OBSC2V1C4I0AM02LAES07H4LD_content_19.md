### Symptom

The following issues may occur after replacing the touchpad hardware.

* The Synaptics touchpad driver cannot be installed after replacing the touchpad from ELAN with Synaptics. Also, if swapping from Synpatics to ELAN, there may be a failure when installing the ELAN touchpad driver. This issue is caused by different hardware ID in the BIOS. For example: The original HW ID is ELAN. After changing to Synaptics, the ID is still ELAN, but the part is Synaptics. This may cause the failure.
* Some touchpad functions are not working after replacing the touchpad hardware (scroll, tap, and so on.)

### Applicable Brands

ideapad

### Operating Systems

* Windows 10
* Windows 11

### Solution

1. Enter BIOS by pressing F2 or Fn+F2 ([Recommended way to enter BIOS for IdeaPad, Lenovo Laptops](https://support.lenovo.com/solutions/ht500216)).
2. Press Fn+F9 to load the default setup to clean the TPID (touchpadID).  
   ![default](https://download.lenovo.com/km/media/images/HT502691/15511_20230718022455859.png)
3. Download and install the latest touchpad driver from the Product Home page (<https://pcsupport.lenovo.com/>). Install the Synaptics or Elan Touchpad driver from the directories that are generated after executing the driver package.  
   ![Drivers and Software](https://download.lenovo.com/km/media/images/HT502691/driversandsoftware2024_20241016133609985.png)  
   ![driver](https://download.lenovo.com/km/media/images/HT502691/2525_20230718022735170.png)  
   ![driver](https://download.lenovo.com/km/media/images/HT502691/321312_20230718022835550.png)

### Related Articles

* [Popular Topics: Tips for PC's](https://support.lenovo.com/solutions/ht503909)
* [Popular Topics: Windows 11, 10](https://support.lenovo.com/solutions/ht118590)
