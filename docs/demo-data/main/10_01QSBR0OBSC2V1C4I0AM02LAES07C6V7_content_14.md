### Symptom

FlexSystem 2500W power supply unit (PSU) from Delta reports one (1) of the following events. All are recovered in a few seconds except the overcurrent fault.

Power Supply xx- Power supply Power Supply xx is off. DC fault.  
Power Supply xx- Power supply Power Supply xx is off. Input fault.  
Power Supply xx- Encountered an internal fan failure.  
Power Supply xx has shut down because of an overcurrent fault.

### Affected Configurations

The system may be any of the following Lenovo servers:

* Flex System Enterprise Chassis, Type 7893, any model
* Lenovo Flex System Enterprise Chassis, Type 8721, any model

This tip is not software specific.

This tip is not option specific.

The system has the symptom described above.

### Solution

Replace the failed PSU with one (1) of the following FRU.

1. Artesyn PSU - FRU 94Y8307 or 00YJ910  
2. Delta PSU   - FRU 00YJ931 (Date code is 78B or above)

\*The date code (D/C) is located on the 4th thru 6th digits from the right of the 11S number. If the PSU has the number 11S00YJ861YK1051711XXX, 711 is the date code.

(where FRU = Field Replaceable Unit)

### Workaround

No workaround.

### Additional Information

Some Delta PSUs use resistors which have quality issues and may potentially cause the misdetection of AC input fault or other fault events while in fact no error conditions have occurred.

If any of the following FRUs has any of the affected date range listed below, it may be exposed to the failure.

FRU Number:  
       69Y5890  
       94Y8303  
       00YJ931

Affected Date Range:  
       54R, 5AT, 5CS, 618, 64N, 672, 6AF, 68B

(where PSU = Power Supply Unit, FRU = Field Replaceable Unit)
