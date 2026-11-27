// duckphone-ble · Android App
//
// 一个 WebView 承载 duckphone 页面，BLE 作为它的传输层。
// 原网页版 firmware/duckphone/ 不改；这里引用的是它的一份只读副本（assets/duckphone）。
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "duckphone-ble"
include(":app")
