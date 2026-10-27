plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
android {
    namespace = "com.aurora.tv"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.aurora.tv"
        minSdk = 21
        targetSdk = 34
        versionCode = 6
        versionName = "0.3.3"
    }
    signingConfigs {
        getByName("debug") {
            storeFile = file("aurora.jks"); storePassword = "aurora123"; keyAlias = "aurora"; keyPassword = "aurora123"
        }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}
dependencies {
    implementation("androidx.media3:media3-exoplayer:1.3.1")
    implementation("androidx.media3:media3-exoplayer-hls:1.3.1")
    implementation("androidx.media3:media3-ui:1.3.1")
    implementation("androidx.media3:media3-common:1.3.1")
    implementation("androidx.media3:media3-datasource:1.3.1")
    implementation("androidx.media3:media3-extractor:1.3.1")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
}
