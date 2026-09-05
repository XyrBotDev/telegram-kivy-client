[app]

# ------------------------------------------------------------
# Application
# ------------------------------------------------------------

title = Telegram Kivy Client

package.name = telegramkivyclient

package.domain = org.example

source.dir = .

source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt

version = 1.0.0


# ------------------------------------------------------------
# Python dependencies
# ------------------------------------------------------------

requirements = python3,kivy,telethon,cryptography


# ------------------------------------------------------------
# Android
# ------------------------------------------------------------

orientation = portrait

fullscreen = 0

android.permissions = INTERNET

android.api = 36

android.minapi = 24

android.archs = arm64-v8a,armeabi-v7a

android.accept_sdk_license = True


# ------------------------------------------------------------
# Python-for-Android
# ------------------------------------------------------------

p4a.branch = develop


# ------------------------------------------------------------
# Build settings
# ------------------------------------------------------------

android.ndk = 29

android.private_storage = True

android.add_src =

android.add_aars =

android.add_jars =

android.add_gradle_repositories =


# ------------------------------------------------------------
# Presplash / icon
# ------------------------------------------------------------

# Uncomment these if you add the files.

# presplash.filename = %(source.dir)s/data/presplash.png
# icon.filename = %(source.dir)s/data/icon.png


# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

log_level = 2


# ------------------------------------------------------------
# Warn on old Android versions
# ------------------------------------------------------------

android.allow_backup = False


[buildozer]

log_level = 2

warn_on_root = 1
