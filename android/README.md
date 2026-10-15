# Android app

This directory contains a native Android WebView wrapper for the `my-expense` web app. It loads the deployed HTTPS frontend; it does not bundle frontend assets or a database.

## What it does

- Opens the HTTPS address supplied through the `serverUrl` Gradle property.
- Uses the Android app name `记账` instead of a browser shortcut.
- Hides the browser address bar because it is a native WebView.
- Shares the deployed frontend, including record deletion and device-local font settings, with iPhone and normal browsers.
- Preserves WebView DOM storage for offline records and settings.

## Build

Open this `android` directory in Android Studio, or run:

```text
gradle assembleDebug -PserverUrl="https://my-expense.phonyslob10.workers.dev"
```

The debug APK is produced at:

```text
app/build/outputs/apk/debug/app-debug.apk
```

A GitHub Actions workflow also builds the APK automatically when files under `android/` change and can be started manually from the Actions tab.

## Changing the server address

Supply `-PserverUrl="https://your-deployment.example"` at build time, or use the `server_url` input of the GitHub Actions workflow. The app's `BuildConfig.SERVER_URL` uses that value. Frontend changes require a separate web deployment; building an APK does not deploy a Worker or run database migrations.
