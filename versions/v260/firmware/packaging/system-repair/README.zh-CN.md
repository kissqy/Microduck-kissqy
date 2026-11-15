R2 / V260 配网、Armbian 启动修复与 USB Ethernet

沿用 V233 配网布局与提交逻辑；替换为用户提供的完整四鸭配图，主题为橘色与奶油白。图片离线内置。系统密码最少 6 位，Wi-Fi WPA 密码最少 8 位。安装后正常重启 Zero 再查看新页面。

安装程序同时部署 USB-C 1 OTG CDC ECM gadget 与 NetworkManager 配置，设备用 `usb0` 通过 DHCP 获取 Mac Internet Sharing 提供的 IPv4 路由，IPv6 使用链路本地地址。新增的 USB 网卡例外保留现有 Wi-Fi 专用管理策略；安装只写文件、校验启用链接并重载 systemd 配置，不启动 gadget 或重启网络，配置在下次开机生效。

服务安装本身不会开启 SSH 或修改账户认证。SSH 仍由设备现有的系统账户与认证设置管理。板端 USB 控制器、Mac 互联网共享及实体网络尚需实机验证。
