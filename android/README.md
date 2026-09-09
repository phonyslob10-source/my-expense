# Android app

This directory contains a small native Android WebView wrapper for the existing `my-expense` web app.

## What it does

- Opens `http://100.109.86.108:3000` directly in an Android app window.
- Uses the Android app name `记账` instead of a browser shortcut.
- Hides the browser address bar because it is a native WebView.
- Keeps the existing frontend unchanged, so iPhone and normal browser use are unaffected.
- Allows HTTP because the service is intentionally reached through the Tailscale network.

## Build

Open this `android` directory in Android Studio, or run:

```text
gradle assembleDebug
```

The debug APK is produced at:

```text
app/build/outputs/apk/debug/app-debug.apk
```

A GitHub Actions workflow also builds the APK automatically when files under `android/` change and can be started manually from the Actions tab.

## Changing the server address

Edit `app/src/main/java/com/phonyslob10/myexpense/MainActivity.java` and change `START_URL` if the Tailscale IP or port changes.
