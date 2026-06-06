# 🧰 Hibernation Troubleshooting Guide

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Lenovo_Logo_20250429174901A001.png)
## 📌 Overview

This article provides a comprehensive guide for troubleshooting hibernation issues on Lenovo devices. It outlines the necessary steps to diagnose and resolve common problems associated with hibernation mode.

## 🔄 Scope Determination

The scope of this guide includes:

* Identifying hibernation-related issues
* Providing step-by-step troubleshooting procedures
* Offering helpful links and FAQs for further assistance

## 📋 Helpful Links

* [Lenovo Support](https://support.lenovo.com/)
* [Windows Power Management](https://docs.microsoft.com/en-us/windows-hardware/drivers/develop/power-management)

## 📋 Questions TSS's Should Be Asking

* Is the hibernation option available on the device?
* Have all necessary drivers been updated?
* Are there any error messages displayed when attempting to enter hibernation?

## 🧰 Troubleshooting Steps

### 🔄 Always Required Troubleshooting

**Note:** If using LogMeIn, it may prevent hibernation from functioning as expected. Complete all troubleshooting steps before testing or guide the customer through these steps without remoting into the machine.

#### Reset Hibernation Functions

1. Open Command Prompt as an administrator.
2. Type `powercfg -h on` and press Enter to enable hibernation.
3. Type `powercfg -h off` and press Enter to disable hibernation.
4. Restart your computer and then re-enable hibernation with `powercfg -h on`.
5. **Issue resolved?**
   
   * **Yes (Y)** → Solution provided
   * **No (N)** → Go to step 2

#### Command Line Fixes

1. Open Command Prompt as an administrator.
2. Run `sfc /scannow` and wait for it to complete.
3. Run `DISM` and wait for it to complete.
4. **Test the issue.**
   
   * **Yes (Y)** → Solution provided
   * **No (N)** → Go to step 3

#### Update Lenovo Drivers

* **BIOS:** If needed, uninstall, restart, and reinstall.
* **Graphics Driver:** If needed, uninstall, restart, and reinstall.
* **Network Driver:** If needed, uninstall, restart, and reinstall.
* **Chipset Drivers:** If needed, uninstall, restart, and reinstall.
* **Update Windows Drivers:** Run "Check for Updates" in the system settings and ensure all updates are applied.

#### Pin Hole Reset

* Conduct a pinhole reset if possible.

#### Reimage

* If all steps above do not resolve the issue, recommend a reimage to the Lenovo base OEM image.

## 📋 FAQs

### What is Hibernation Mode?

Hibernation mode is designed primarily for laptops and may not be available on all PCs. It uses less power than sleep mode and allows you to resume your work exactly where you left off, although it may take longer to start up compared to sleep mode.

**Hibernation mode uses the S4 power state:**

* **S4 - Hibernate:** Your device appears to be off, using the lowest level of power consumption. It saves the contents of volatile memory to a hibernation file, allowing for restoration of the working context upon startup.

### How to Turn Off Hibernation Mode

1. Open the Start menu by pressing the Windows button.
2. Search for `cmd`.
3. Right-click Command Prompt in the search results and select **Run as Administrator**.
4. Select **Continue** when prompted by User Account Control.
5. Type `powercfg.exe /hibernate off` at the command prompt and press Enter.
6. Type `exit` and press Enter to close the Command Prompt window.

## ⚠️ Known Issues

* Some users may experience difficulties with hibernation if third-party software interferes with power management settings. Always ensure that all software is up to date and compatible with the operating system.

For further assistance, please refer to the helpful links provided above or contact Lenovo support.
