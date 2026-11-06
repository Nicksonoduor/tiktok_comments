[app]

title = TikTok Comment Downloader
package.name = tiktokcommentdownloader
package.domain = org.nickson
source.dir = .
source.include_exts = py,kv,png,wav
source.exclude_dirs = .git,.github,.buildozer,bin,__pycache__,venv,.venv
version = 1.0
requirements = python3==3.11.9,kivy==2.3.1,kivymd==1.2.0,requests==2.33.1
orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/icon.png

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 23
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]

log_level = 2
warn_on_root = 1
