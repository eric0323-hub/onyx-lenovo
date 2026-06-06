| Symptom |
| --- |

NVIDIA graphics driver 9.18.13.4788 may cause a false hang after waking up from the Hibernation (S4) Power State if the system is connected to a monitor with a DisplayPort/mini DisplayPort to HDMI dongle. After approximately 5 minutes, the symptom will disappear and the system will resume properly.

| Affected configurations |
| --- |

The above symptom is associated with, but not limited to, the following systems:

* ThinkStation

Affected Systems (machine types, model types):

* ThinkStation P300 (Type 30AJ, 30AK, 30AG, 30AH)

System is configured with:

* For Microsoft Windows 8.1 operating, NVIDIA graphic cards with display ports to HDMI Dongle (Lenovo P/N: 0B51675, FRU P/N: 03T8404)
* For Microsoft Windows 8.1 operating, NVIDIA graphic cards with mini-display ports to HDMI Dongle (Lenovo P/N: 0C19459, FRU P/N: 03T8318)

Operating System

* Microsoft Windows 8.1

| Solution |
| --- |

Check the NVIDIA graphic driver version via the “Device Management” or NVIDIA control panel. If the version is 9.18.13.4788, then download the latest driver (9.18.13.4803 or higher) to resolve this issue:

1. If the NVIDIA graphic driver version is 9.18.13.4788, then [download the latest version](http://support.lenovo.com/au/en/products/workstations/thinkstation-p-series-workstations/thinkstation-p300?c=1) to update.
2. If the system is recovered with a RDVD and the NVIDIA graphic driver version is 9.18.13.4788:
   
   * [Download the latest RDVD driver version after 5.27.2015](http://support.lenovo.com/au/en/products/workstations/thinkstation-p-series-workstations/thinkstation-p300?c=1)

| Additional Information |
| --- |

This symptom only appears with the below configurations at the same time:

* Microsoft Windows 8.1
* NVIDIA Graphic Driver 9.18.13.4788
* Display Port to HDMI Dongle or Mini-Display Port to HDMI Dongle or both
