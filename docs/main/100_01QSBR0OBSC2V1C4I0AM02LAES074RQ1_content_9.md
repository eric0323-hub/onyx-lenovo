### Symptom

The system may hang during 1 of 2 scenarios

(1) The system may hang at Lenovo logo screen during restart

(2) The system may hang with black screen after waking from S4/S5

### Applicable Brands

ThinkStation

### Applicable Systems

* ThinkStation P340
* ThinkStation P350
* ThinkStation P520
* ThinkStation P520c
* ThinkStation P720
* ThinkStation P920
* ThinkStation P620

### System Is Configured With

T400

### Operating Systems

Windows 10 64-bit

### Solution

Update the T400 VBIOS to version: 90.17.7F.00.1B or later.

Try to refresh the graphics card VBIOS after successfully booting into the system or replace the 2k monitor to refresh.

VBIOS Update step:

1. Boot to the windows

2. Open Command prompt by Administrator

3. Perform the following operations

1) Boot to the directory where the refresh file is located

command: cd directory

2) Perform the flash command

command: nvflash.exe T400.rom --auto

3) Reboot the system

Refer to the following image:

![Flash T400 VBIOS](https://download.lenovo.com/km/media/images/HT512766/Flash T400 VBIOS_20210819075014112.jpg)

T400 VBIOS and Flash Tool:

<https://download.lenovo.com/km/media/attachment/T400 VBIOS and NVFlash.zip>​
