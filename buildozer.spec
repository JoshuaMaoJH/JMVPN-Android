[app]

title = JMVPN
package.name = jmvpn
package.domain = org.jmvpn

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ico,json

version = 2.0

requirements = python3,kivy,paramiko,pysocks,pillow

presplash.filename = %(source.dir)s/icon.ico
icon.filename = %(source.dir)s/icon.ico

orientation = portrait

fullscreen = 0

android.archs = arm64-v8a

android.permissions = INTERNET

android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.build_tools_version = 33.0.2
android.accept_sdk_license = True

# (str) Android entry point, default is ok for Kivy-based app
#android.entrypoint = org.kivy.android.PythonActivity

# (str) Full name including package path of the Java class that implements Android Activity
# use that parameter together with android.entrypoint to set custom Java class instead of PythonActivity
#android.activity_class_name = org.kivy.android.PythonActivity

[buildozer]

log_level = 2

warn_on_root = 1
