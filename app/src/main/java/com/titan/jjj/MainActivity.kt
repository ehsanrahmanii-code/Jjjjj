package com.titan.jjj

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var swipe: SwipeRefreshLayout
    private lateinit var progress: ProgressBar
    private lateinit var statusPanel: View
    private lateinit var statusText: TextView
    private lateinit var btnRetry: Button
    private lateinit var btnGuide: Button

    private val engineUrl = "http://127.0.0.1:8080/"
    private val handler = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor()
    private val engineStarting = AtomicBoolean(false)
    private val engineStarted = AtomicBoolean(false)

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        webView = findViewById(R.id.webview)
        swipe = findViewById(R.id.swipe)
        progress = findViewById(R.id.progress)
        statusPanel = findViewById(R.id.status_panel)
        statusText = findViewById(R.id.status_text)
        btnRetry = findViewById(R.id.btn_retry)
        btnGuide = findViewById(R.id.btn_guide)
        setupWebView()
        swipe.setOnRefreshListener { tryLoadUi() }
        btnRetry.setOnClickListener { startEngineAndLoad() }
        btnGuide.setOnClickListener {
            statusText.text = getString(R.string.guide_full)
            statusPanel.visibility = View.VISIBLE
        }
        statusText.text = getString(R.string.boot_engine)
        startEngineAndLoad()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        val s = webView.settings
        s.javaScriptEnabled = true
        s.domStorageEnabled = true
        s.databaseEnabled = true
        s.allowFileAccess = true
        s.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        s.cacheMode = WebSettings.LOAD_DEFAULT
        s.useWideViewPort = true
        s.loadWithOverviewMode = true
        s.builtInZoomControls = false
        s.displayZoomControls = false
        s.userAgentString = s.userAgentString + " TITAN-PRO/1.0"
        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                progress.visibility = if (newProgress in 1..99) View.VISIBLE else View.GONE
                progress.progress = newProgress
            }
        }
        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                progress.visibility = View.VISIBLE
            }
            override fun onPageFinished(view: WebView?, url: String?) {
                progress.visibility = View.GONE
                swipe.isRefreshing = false
                statusPanel.visibility = View.GONE
                webView.visibility = View.VISIBLE
            }
            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                if (request?.isForMainFrame == true) showOffline()
            }
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val u = request?.url?.toString() ?: return false
                if (u.startsWith("http://127.0.0.1") || u.startsWith("http://localhost")) return false
                try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(u))) } catch (_: Exception) {}
                return true
            }
        }
    }

    private fun startEngineAndLoad() {
        statusPanel.visibility = View.VISIBLE
        webView.visibility = View.INVISIBLE
        statusText.text = getString(R.string.boot_engine)
        progress.visibility = View.VISIBLE
        io.execute {
            try {
                handler.post { statusText.text = "Python runtime…" }
                if (!Python.isStarted()) Python.start(AndroidPlatform(applicationContext))
                handler.post { statusText.text = "Starting TITAN engine…" }
                if (engineStarted.compareAndSet(false, true) || !probeEngine()) {
                    if (engineStarting.compareAndSet(false, true)) {
                        try {
                            val boot = Python.getInstance().getModule("titan_boot")
                            val result = boot.callAttr("start_server").toString()
                            handler.post { statusText.text = getString(R.string.engine_result, result) }
                        } catch (e: Exception) {
                            handler.post { statusText.text = getString(R.string.engine_fail, e.message ?: "error") }
                        } finally {
                            engineStarting.set(false)
                        }
                    }
                }
                var ok = false
                repeat(120) { i ->
                    if (probeEngine()) { ok = true; return@repeat }
                    try {
                        val st = Python.getInstance().getModule("titan_boot").callAttr("get_status_text").toString()
                        handler.post { statusText.text = "${i + 1}/120 · $st" }
                    } catch (_: Exception) {
                        handler.post { statusText.text = getString(R.string.boot_engine) + "\n(${i + 1}/120)" }
                    }
                    Thread.sleep(2000)
                }
                handler.post { if (ok) tryLoadUi() else showOffline() }
            } catch (e: Exception) {
                handler.post {
                    statusText.text = getString(R.string.engine_fail, e.message ?: "error")
                    showOffline()
                }
            }
        }
    }

    private fun tryLoadUi() {
        statusText.text = getString(R.string.connecting)
        webView.loadUrl(engineUrl)
    }

    private fun showOffline() {
        swipe.isRefreshing = false
        progress.visibility = View.GONE
        webView.visibility = View.INVISIBLE
        statusPanel.visibility = View.VISIBLE
        if (statusText.text.isNullOrBlank()) statusText.text = getString(R.string.engine_offline)
    }

    private fun probeEngine(): Boolean {
        return try {
            val c = URL(engineUrl).openConnection() as HttpURLConnection
            c.connectTimeout = 1500
            c.readTimeout = 1500
            c.requestMethod = "GET"
            c.instanceFollowRedirects = false
            val code = c.responseCode
            c.disconnect()
            code in 200..399
        } catch (_: Exception) { false }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        webView.destroy()
        super.onDestroy()
    }
}
