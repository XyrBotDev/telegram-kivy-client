[app]

title = Telegram Kivy Client
package.name = telegramkivyclient
package.domain = org.example.telegram

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt
source.exclude_dirs = .buildozer,.git,build,dist,.github
source.exclude_patterns = .gitignore,.git*,*.pyc,*.pyo,__pycache__

version = 1.0.0

requirements = python3,kivy,telethon
p4a.python_version = 3.12

orientation = portrait
fullscreen = 0

android.permissions = INTERNET

android.api = 36
android.minapi = 24
android.archs = arm64-v8a

android.accept_sdk_license = True

p4a.branch = develop

android.ndk = 29

android.private_storage = True

log_level = 2


[buildozer]

log_level = 2
warn_on_root = 1
