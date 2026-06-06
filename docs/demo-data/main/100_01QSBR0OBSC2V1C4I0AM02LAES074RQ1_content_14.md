# Understanding Sleep States 💻

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Lenovo_Logo_20250429174901A001.png)

Modern computing systems utilize various sleep states to manage power consumption while retaining memory, allowing for quick resumption of operations. These states are defined by the Advanced Configuration and Power Interface (ACPI) standard. The key sleep states include S1, S2, S3, and S4, each representing a different level of power conservation.

## Overview of Sleep States 🔄

Each sleep state reduces system power usage in a graduated manner, with deeper states providing more energy savings at the cost of higher entry/wake latency. Windows treats each of these states as "Sleep".

### S0 (Modern Standby/Connected Standby)

* The computer is powered on and in a normal active state.
* Resumption is instant, as very few components are actually off.
* Background tasks may continue to operate, including downloading updates.
* The CPU is in a low-powered state but remains fully on.
* Battery drain may be significant, comparable to leaving the computer on with the screen off; however, the actual savings depend on background activity.

### S1

* The CPU is stopped, but memory is retained.
* Most components are powered down.
* The device can enter and wake within microseconds.
* No hardware information is lost; power still flows through the CPU to maintain the last known clock cycle and cache.

### S2

* Similar to S1 but with deeper suspension of system components.
* Some CPU and cache information may be lost, while memory is fully maintained.

### S3 (Traditional Sleep)

* The system enters a standby mode with only RAM powered to retain memory.
* Other components, including the CPU, are powered off, and some information may be lost, although it may save some data in RAM to assist with resumption.
* This was the traditional method of sleep before the advent of instant power-on modes.
* Resumption may take a few seconds.

### S4 (Hibernate/Shut Down with Fast Startup Enabled)

* Commonly referred to as "Hibernate."
* The system saves RAM contents to a disk file (hiberfil.sys) and then powers off completely.
* Upon powering back on, the system restores its state from the hibernation file.
* This is what "shutting down" with Fast Startup enabled does, which is why entering the BIOS from this state is not possible.
* Depending on hard drive speed and the amount of RAM saved, resumption can take from several seconds to up to one minute.

## Wake Events and External Indicators 🔍

Certain events can wake the system from sleep states, including:

* User input
* Scheduled tasks
* External devices (e.g., network cards)

Some systems may include indicators (e.g., LED lights) to show that the system is in a sleep state.

### Troubleshooting Wake Events

To analyze wake events, you can use the following commands:

* **Power Sleep Study**: Run `powercfg /sleepstudy` to see how often sleep is interrupted.
* **Last Wake Event**: Use `powercfg -lastwake` to find out what caused the system to wake up last. This is particularly useful for troubleshooting devices that seem to wake up unexpectedly.

## Valid Sleep States

See which sleep states are currently available:   
**powercfg /a**  


![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Powercfg-a-command_20250429175955A110.png)
## Further reading

[System Sleeping States - Windows drivers | Microsoft Learn](https://learn.microsoft.com/en-us/windows-hardware/drivers/kernel/system-sleeping-states)

[ACPI - Wikipedia](https://en.wikipedia.org/wiki/ACPI#Device_states)
