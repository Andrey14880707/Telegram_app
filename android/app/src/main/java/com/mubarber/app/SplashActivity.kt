package com.mubarber.app

import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import android.view.animation.AnimationUtils
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

@SuppressLint("CustomSplashScreen")
class SplashActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_splash)

        val logo = findViewById<ImageView>(R.id.splashLogo)
        val title = findViewById<TextView>(R.id.splashTitle)
        val sub = findViewById<TextView>(R.id.splashSub)

        val fadeIn = AnimationUtils.loadAnimation(this, android.R.anim.fade_in)
        fadeIn.duration = 700
        logo.startAnimation(fadeIn)

        val fadeInDelay = AnimationUtils.loadAnimation(this, android.R.anim.fade_in)
        fadeInDelay.duration = 800
        fadeInDelay.startOffset = 300
        title.startAnimation(fadeInDelay)

        val fadeInDelay2 = AnimationUtils.loadAnimation(this, android.R.anim.fade_in)
        fadeInDelay2.duration = 800
        fadeInDelay2.startOffset = 500
        sub.startAnimation(fadeInDelay2)

        // перейти на главный экран через 1.8 сек
        window.decorView.postDelayed({
            startActivity(Intent(this, MainActivity::class.java))
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out)
            finish()
        }, 1800)
    }
}
