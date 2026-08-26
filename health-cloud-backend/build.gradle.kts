plugins {
    java
    id("org.springframework.boot") version "3.2.0" apply false
    id("io.spring.dependency-management") version "1.1.4" apply false
}

allprojects {
    group = "com.health"
    version = "1.0.0"
    repositories {
        mavenCentral()
    }
}
