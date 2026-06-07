# 📌 ISP-Related Network Issues

![](https://ukm.lenovo.com/prod-api/file/download?key=2025/04/29/Lenovo_Logo_20250429174901A001.png)

This article addresses common network issues related to Internet Service Providers (ISPs), specifically focusing on symptoms, causes, and solutions for users experiencing connectivity problems.

## Symptoms

* Websites partially load.
* Some websites load while others do not.

## Cause

Verizon FiOS routers may force the DNS suffix to `mynetworksettings.com`, which can lead to connectivity issues.

## 🧰 Troubleshooting Steps

1. **Disable IPv6**:
   
   * Access your router settings and disable the IPv6 option.
2. **Contact Support**:
   
   * If the issue persists after disabling IPv6, advise the user to contact Verizon Support for further assistance.

## 🔄 Workaround

If the problem continues, consider using a third-party DNS service. Here are some recommended options:

* **Google DNS**:
  
  + Primary: `8.8.8.8`
  + Secondary: `8.8.4.4`
* **Cloudflare DNS**:
  
  + Primary: `1.1.1.1`

By following these steps, users can resolve ISP-related network issues and improve their browsing experience.
