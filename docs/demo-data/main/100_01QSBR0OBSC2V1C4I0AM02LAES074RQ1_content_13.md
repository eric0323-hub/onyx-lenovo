# 🧰 Lid Sensor Troubleshooting Guide

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Lenovo_Logo_20250429174901A001.png)

This article provides an overview of the lid sensor functionality in laptops, potential issues related to the sensor, and guidance on how to identify and resolve these issues.

## 📌 Overview of Lid Sensor Functionality

The lid sensor is responsible for detecting whether the laptop lid is open or closed. It consists of:

* A **hall-effect sensor** located on either the screen or keyboard side of the laptop.
* A **magnet** positioned on the facing part of the laptop.

When the sensor detects a magnetic field, it assumes that the lid is closed.

## ⚠️ Possible Sensor-Related Issues

If you encounter any of the following issues, they may be related to the lid sensor:

* The screen remains on when the lid is closed, despite being configured to sleep or power off.
* The flip-to-start feature in BIOS is enabled but does not activate.
* The device does not sleep after ruling out software issues.
* Sensor errors are detected during the F10 Diagnostic.

## 🔍 Identifying the Location of the Sensor

To locate the lid sensor and its corresponding magnet, follow these steps:

1. Open PC support and review the images of the stock parts.
2. Check the **C-cover** for a magnet near the edge opposite the hinge. It typically appears as a small silver rectangle or square, measuring about 0.5-1 cm in length. (Refer to the attached example; note that the size and shape may vary by model.)
3. **Possible configurations**:
   
   * **Magnet on C-cover**: The sensor is connected with an EDP cable or is part of the A-cover or a subcard on the A-cover.
   * **Magnet on A-cover**: The sensor may be located on a subcard or system board (SB).
   * **No magnet on either cover**: If the pictures are inconclusive, contact the TSS floor or consult with the Team Lead queue.

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Magnet_20250429175407A070.png)
## ⚙️ Sensor Hardware Issues Not Related to the Sensor Itself

If you find no magnet on either the C-cover or A-cover of the device, consider the following:

* The magnet may have fallen out due to:
  
  + A drop.
  + Customer-induced damage (CID) during self-repair or maintenance.
  + Technician-induced damage (TID) from a previous onsite or depot repair.

### Additional Checks

* If the device is unexpectedly going to sleep or displaying the lock screen, check for external magnets that may be causing interference. Common sources include:
  
  + Wearable devices.
  + Phone cases.
  + Third-party camera privacy shutters.
* Ensure the laptop is not placed directly on top of another laptop or a stack of devices, as the lid sensor magnets from those devices may interfere with the sensor's functionality.

By following this guide, you can effectively troubleshoot and resolve issues related to the lid sensor in your laptop. If problems persist, consider reaching out to technical support for further assistance.
