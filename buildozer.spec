[app]
title = MyChat
package.name = mychat
package.domain = org.mychat.lan
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt
version = 20260924.A1
requirements = python3,kivy
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE,CHANGE_WIFI_STATE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
