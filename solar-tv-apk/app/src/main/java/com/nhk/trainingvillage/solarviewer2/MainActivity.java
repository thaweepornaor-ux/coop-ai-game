package com.nhk.trainingvillage.solarviewer2;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.WindowManager;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Toast;

public final class MainActivity extends Activity {
    private static final String OVERVIEW = "https://sg5.fusionsolar.huawei.com/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=31287950-c5f9-482d-ad0a-3932c438d895#/view/station/NE=89158756/overview";
    private WebView web;
    private SharedPreferences prefs;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        prefs = getSharedPreferences("NHK_SOLAR_TV", MODE_PRIVATE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON | WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
            View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION |
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);
        web = new WebView(this);
        web.setFocusable(true);
        web.setFocusableInTouchMode(true);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setMediaPlaybackRequiresUserGesture(false);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override public void onPageFinished(WebView view, String url) {
                CookieManager.getInstance().flush();
            }
        });
        setContentView(web);
        web.requestFocus();
        load();
    }

    private String destination() { return prefs.getString("kiosk_url", OVERVIEW); }
    private void load() { web.loadUrl(destination()); }

    private void menu() {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        int pad = (int)(18 * getResources().getDisplayMetrics().density);
        form.setPadding(pad, pad, pad, pad);
        EditText url = new EditText(this);
        url.setSingleLine(false);
        url.setMinLines(2);
        url.setHint("วางลิงก์ Huawei Kiosk View (HTTPS) ถ้ามี");
        String configured = prefs.getString("kiosk_url", "");
        url.setText(configured.equals(OVERVIEW) ? "" : configured);
        form.addView(url);
        new AlertDialog.Builder(this)
            .setTitle("NHK Solar TV – ตั้งค่าจอ")
            .setMessage("หาก Huawei ขอ Login ให้เข้าสู่ระบบตามปกติ หรือใช้ลิงก์ Kiosk ที่สร้างจาก Huawei เพื่อเปิดจอโดยไม่ต้อง Login")
            .setView(form)
            .setPositiveButton("บันทึก Kiosk", (d, v) -> {
                String entered = url.getText().toString().trim();
                Uri parsed = Uri.parse(entered);
                if (!"https".equalsIgnoreCase(parsed.getScheme()) || parsed.getHost() == null) {
                    Toast.makeText(this, "ลิงก์ต้องขึ้นต้นด้วย https://", Toast.LENGTH_LONG).show();
                    return;
                }
                prefs.edit().putString("kiosk_url", entered).apply();
                load();
            })
            .setNegativeButton("ใช้ Overview เดิม", (d, v) -> {
                prefs.edit().remove("kiosk_url").apply();
                load();
            })
            .setNeutralButton("เปิดด้วยเบราว์เซอร์", (d, v) -> {
                try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(web.getUrl() == null ? destination() : web.getUrl()))); }
                catch (Exception e) { Toast.makeText(this, "ไม่พบแอปเบราว์เซอร์ในกล่องทีวี", Toast.LENGTH_LONG).show(); }
            })
            .show();
    }

    @Override public boolean onKeyUp(int key, KeyEvent event) {
        if (key == KeyEvent.KEYCODE_MENU || key == KeyEvent.KEYCODE_SETTINGS) {
            menu(); return true;
        }
        return super.onKeyUp(key, event);
    }
    @Override public void onBackPressed() {
        menu();
    }
    @Override protected void onPause() {
        if (web != null) CookieManager.getInstance().flush();
        super.onPause();
    }
    @Override protected void onDestroy() {
        if (web != null) web.destroy();
        super.onDestroy();
    }
}
