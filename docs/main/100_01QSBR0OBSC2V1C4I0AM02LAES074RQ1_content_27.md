## Symptom

With this setting configured, closing the LCD lid and connecting to the docking station causes the system to enter sleep mode. After that, the system cannot be woken up using the mouse or keyboard.

Setting:

1. When I close the lid with plugged in - " Do nothing"
   
   ![](https://ukm.lenovo.com/prod-api/file/download?key=accessory/8841e567988943a6ba44299c600bd500-1764668091375.png&name=image..png)
2. BIOS - Config - Power On with AC Attach "On"
   
   ![](https://ukm.lenovo.com/prod-api/file/download?key=accessory/df3646ea8f6743b98b1da83544a5cb13-1764668078772.png&name=image..png)

## Applicable Systems

ThinkPad with Windows 11

## Solution

Find the 'EnableInputSuppression' registry under the following location: HKEY\_LOCAL\_MACHINE\SYSTEM\CurrentControlSet\Control\Power.

Change it from 1 to 0, then reboot to see if that makes any difference.

![](https://ukm.lenovo.com/prod-api/file/download?key=accessory/33be2e8d8a1d47e3a4f70640667d767e-1764668249287.png&name=image..png)
