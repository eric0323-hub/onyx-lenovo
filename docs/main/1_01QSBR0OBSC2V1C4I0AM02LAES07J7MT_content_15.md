# 🧰 Ethernet Port Issue on Docks

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Lenovo_Logo_20250429174901A001.png)
## 📌 Symptom

Users may experience issues with the Ethernet port on docks, where the Ethernet connection does not pass through to the system.

## 🔍 Cause

This issue typically arises when Windows performs an update that installs an updated driver, which can disrupt the Ethernet functionality. Specifically, the **Lenovo USB 3.0 LAN Driver** for docks and adapters is known to cause this problem.

## ⚙️ Solution

To resolve this issue, follow these steps:

1. **Download the Realtek Driver**:
   
   * For **Windows 11**: Download the **Realtek USB FE / GBE / 2.5G Ethernet Family Controller** version **11.9.0823.2022\_20\_10262022**.
   * For **Windows 10**: Download version **V.10055.20\_09212022**.
2. **Installation**:
   
   * Visit the <https://www.realtek.com/Download/List?cate_id=584> to access the drivers.
   * Follow the installation instructions provided on the website.
3. **Restart Your System**:
   
   * After installation, restart your computer to ensure the changes take effect.

By following these steps, the Ethernet functionality on your dock should be restored. If issues persist, consider checking for additional updates or contacting support for further assistance.
