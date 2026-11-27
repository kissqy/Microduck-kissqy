import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// 发布签名：key 和口令不进仓库。缺 keystore.properties 时 release 走未签名产物，
// 调试构建完全不受影响。
val keystoreProps: Properties? = rootProject.file("keystore.properties")
    .takeIf { it.exists() }
    ?.let { file -> Properties().apply { file.inputStream().use { load(it) } } }

android {
    namespace = "com.microduck.phone"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.microduck.phone"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    signingConfigs {
        if (keystoreProps != null) {
            create("release") {
                storeFile = rootProject.file(keystoreProps.getProperty("storeFile"))
                storePassword = keystoreProps.getProperty("storePassword")
                keyAlias = keystoreProps.getProperty("keyAlias")
                keyPassword = keystoreProps.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = keystoreProps?.let { signingConfigs.getByName("release") }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    // 页面是 firmware/duckphone/static 的单向副本，由 tools/sync-web.sh 同步。
    // ble-bridge.js 放在 assets/ 根上，不在 duckphone/ 里，所以同步的 --delete 不会删它。
    sourceSets["main"].assets.srcDirs("src/main/assets", rootProject.file("../assets"))
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.webkit:webkit:1.12.1")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
