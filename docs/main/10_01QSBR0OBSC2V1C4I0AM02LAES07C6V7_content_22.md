### Symptom

The system battery icon shows the battery is not charging when connected to the AC adapter. For general battery issues, refer to [Troubleshooting Battery Issues - PC](http://support.lenovo.com/solutions/HT080185).

Perform the following checks:

* The system manufacture date is prior to 2021/07 (YYYY/MM). The following image shows an example of  the system Serial label with the manufacture date circled.  
  ![System Label](https://download.lenovo.com/km/media/images/HT512607/system label_20210712165303598.jpg)
* Use Lenovo Vantage to check the battery FRU Part Number and FW (firmware) version. Launch the Lenovo Vantage application and select **My Device**, **Power View**, See **Battery Details**. Check if your battery's FRU and firmware version match the FRU P/N and Prior FW (firmware) level in the table below.  
  ![Battery](https://download.lenovo.com/km/media/images/HT512607/Vantage Battery_20210712165214957.jpg)
  
  |
  |  |
  | ASM P/N | **FRU P/N** | FRU Description | **Prior FW** | **New FW** |
  | SB10W51928 | **5B10W51829** | Internal, 3c, 50Wh, LiIon, CXP | 0006-0108-0101-0008 | 0006-0108-0101-0009 |
  | SB10W51929 | **5B10W51830** | Internal, 3c, 50Wh, LiIon, CXP | 0006-0109-0103-0007 | 0006-0109-0103-0008 |
  | SB10T83204 | **5B10W13961** | Internal,6c,68Wh, LiIon,CXP | 0006-0087-0102-0008 | 0006-0087-0102-0009 |
  | SB10T83217 | **5B10W13974** | Internal,4c,57Wh,LiIon,CXP | 0006-009E-0101-0008 | 0006-009E-0101-0009 |
  | SB10T83127 | **5B10W13884** | Internal, 4c, 50Wh, LiIon, CXP | 0006-0079-0103-000A | 0006-0079-0103-000B |
  | SB10T83207 | **5B10W13964** | Internal,3c,48.2Wh,LiIon,CXP | 0006-008F-0101-0008 | 0006-008F-0101-0009 |
  | SB10Z26488 | **5B10Z26487** | CP/C L19C4PG3 7.72V42Wh4cell | 0006-0094-0101-0007 | 0006-0094-0101-0008 |

### Applicable Brands

ThinkPad

### Applicable Systems

* T14 Gen 2 (Machine Types: 20W0, 20W1)
* P14s Gen2 (Machine Types: 20VX, 20VY)
* T14 Gen 2 AMD (Machine Types: 20XK, 20XL)
* P14s Gen 2 AMD (Machine Types: 21A0, 21A1)
* X1 Yoga Gen 6 (Machine Types: 20XY, 20Y0)
* X1 Carbon Gen 9 (Machine Types: 20XW, 20XX)
* P15v Gen 1 (Machine Types: 20TQ, 20TR)
* T15p Gen 1 (Machine Types: 20TN, 20TM)
* X1 Fold Gen 1 (Machine Types: 20RK, 20RL)
* X1 Nano Gen 1 (Machine Types: 20UN, 20UQ)
* X12 Detachable Gen 1 (Machine Types: 20UW, 20UV) ​

### Operating Systems

* Windows 10
* Windows 11

### Solution

Update the battery firmware.

Lenovo recommends applying the updated battery firmware to applicable systems/batteries immediately to prevent and recover from the described symptom. Use any of the following methods to obtain the Lenovo Battery Firmware Update Utility and install the Firmware:

* Lenovo Vantage: System Update  
  
  Run **System Update**, select the Lenovo Battery Firmware Update Utility and install it.
* Download the Lenovo Battery Firmware Update Utility from the Lenovo support site and install it by following the README instructions.
  1. Visit [Lenovo Support](http://support.lenovo.com/).
  2. Detect or select product (view option).
  3. Select **Drivers & Software**.
  4. Choose **Select Drivers** under **Manual Update**.
  5. Select **Software and Utilities**.
* Manually download the update from [Lenovo Battery Firmware Update Utility for Windows 10 (32-bit, 64-bit) - ThinkPad](https://support.lenovo.com/downloads/DS550872) and install it.

### Additional Information

Additionally, from the Windows PowerShell or Command Prompt, use the **powercfg /batteryreport** command to generate a battery report. Follow the output path to find battery-report.html, which can be viewed in a web browser. The battery report has the FRU information next to the battery name.

![Installed batteries](https://download.lenovo.com/km/media/images/HT512607/Windows11batteryfru_20250926124208557.png)

### Related Articles

* [Lenovo Vantage: Using your PC just got easier](https://support.lenovo.com/solutions/ht505081)
* [How to navigate and download Lenovo software or drivers from Lenovo Support Site](https://support.lenovo.com/solutions/HT117260)
