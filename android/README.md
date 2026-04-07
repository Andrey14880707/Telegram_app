# München Barber — Android APK

WebView-обёртка для `https://www.mubarber.com`.

## Структура

```
android/
  app/src/main/
    java/com/mubarber/app/
      SplashActivity.kt    — золотой splash screen 1.8с
      MainActivity.kt      — WebView + file upload + back nav
    res/
      layout/              — activity_splash.xml, activity_main.xml
      values/              — strings, colors, themes
      drawable/            — ic_logo.xml (MB monogram SVG)
      xml/                 — file_paths.xml (FileProvider)
    AndroidManifest.xml
```

## Как собрать APK

### Вариант 1 — Android Studio (рекомендуется)

1. Открой Android Studio → **File → Open** → папка `android/`
2. Дождись sync Gradle
3. **Build → Build Bundle(s) / APK(s) → Build APK(s)**
4. APK в `app/build/outputs/apk/debug/app-debug.apk`

### Вариант 2 — командная строка

```bash
# Убедись что ANDROID_HOME установлен
export ANDROID_HOME=$HOME/Android/Sdk

cd android
./gradlew assembleDebug

# APK будет здесь:
# app/build/outputs/apk/debug/app-debug.apk
```

### Release APK (для публикации)

1. Создай keystore:
   ```bash
   keytool -genkey -v -keystore mubarber-release.jks \
     -keyalg RSA -keysize 2048 -validity 10000 \
     -alias mubarber
   ```

2. В `app/build.gradle.kts` добавь `signingConfigs { release { ... } }`

3. ```bash
   ./gradlew assembleRelease
   ```

## Что умеет приложение

- Загружает `https://www.mubarber.com` в WebView
- Поддержка загрузки фото/видео из галереи (для ленты/Cloudinary)
- Съёмка фото прямо через камеру
- Кнопка Back — навигация назад по истории WebView
- Тел/почта ссылки открываются в системных приложениях
- Адаптивная иконка (тёмный фон + MB монограмма золотом)
- Золотой progress bar при загрузке страниц
- Полноэкранное видео

## Требования

- Android Studio Ladybug (2024.1+) или Gradle 8.5+
- Android SDK API 26+ (Android 8.0)
- JDK 17
