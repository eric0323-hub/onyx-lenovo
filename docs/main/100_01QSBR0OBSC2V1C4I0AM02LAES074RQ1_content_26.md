### Symptom

The system restarts unexpectedly when waking from sleep or hibernate.

The following steps reproduce the issue (from sleep):

1. Boot to Red Hat 8.4.
2. Disable WOL (ethtool -s enp2s0 wol d ).
3. Enter S3 (Systemctl suspend).
4. Wake up system.
5. After entering the operating system, the system restarts.

The following steps reproduce the issue (from hibernate):

1. Boot to Red Hat 8.4.
2. Enter S4 (Systemctl hibernate).
3. Wake up system.
4. After entering the operating system, the system restarts.

### Applicable Brands

ThinkStation

### Applicable Systems

ThinkStation P350

### System Is Configured With

Aquantia PCIex4 10GbE AQN-107 Gigabit Ethernet Adapter

### Operating Systems

Red Hat Enterprise Linux 8.4

### Limitations

This is a Red Hat Enterprise Linux 8.4 limitation.

### Workaround

Replace Aquantia PCIex4 10GbE AQN-107 with a different ethernet adapter.
