package com.phonyslob10.myexpense;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.webkit.ConsoleMessage;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final String TAG = "MyExpenseWebView";
    private static final String START_URL = "http://100.109.86.108:3000";
    private WebView webView;
    private TextView errorView;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setSupportZoom(false);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                super.onPageStarted(view, url, favicon);
                hideError();
                Log.d(TAG, "Page started: " + url);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                Log.d(TAG, "Page finished: " + url);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);
                if (request.isForMainFrame()) {
                    int code = error != null ? error.getErrorCode() : 0;
                    String description = error != null && error.getDescription() != null
                            ? error.getDescription().toString() : "Unknown WebView error";
                    String url = request.getUrl() != null ? request.getUrl().toString() : START_URL;
                    Log.e(TAG, "Main frame load error: code=" + code + ", description=" + description + ", url=" + url);
                    showError(code, description, url);
                }
            }

            @SuppressWarnings("deprecation")
            @Override
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                super.onReceivedError(view, errorCode, description, failingUrl);
                Log.e(TAG, "Legacy load error: code=" + errorCode + ", description=" + description + ", url=" + failingUrl);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage consoleMessage) {
                Log.d(TAG, "JS console: " + consoleMessage.message() + " @ "
                        + consoleMessage.sourceId() + ":" + consoleMessage.lineNumber());
                return true;
            }
        });

        webView.loadUrl(START_URL);
    }

    private void showError(int code, String description, String url) {
        if (errorView == null) {
            errorView = new TextView(this);
            errorView.setTextSize(16);
            errorView.setPadding(40, 60, 40, 60);
            errorView.setTextIsSelectable(true);
            errorView.setBackgroundColor(0xFFFFFFFF);
            errorView.setOnClickListener(v -> {
                hideError();
                webView.loadUrl(START_URL);
            });
            addContentView(errorView, new android.view.ViewGroup.LayoutParams(
                    android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                    android.view.ViewGroup.LayoutParams.MATCH_PARENT));
        }

        String message = "记账页面加载失败\n\n"
                + "错误码：" + code + "\n"
                + "原因：" + description + "\n"
                + "地址：" + url + "\n\n"
                + "点击此处重试";
        errorView.setText(message);
        errorView.setVisibility(View.VISIBLE);
    }

    private void hideError() {
        if (errorView != null) {
            errorView.setVisibility(View.GONE);
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
        }
        super.onDestroy();
    }
}
