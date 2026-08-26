plugins {
    java
    id("org.springframework.boot")
    id("io.spring.dependency-management")
}

dependencies {
    implementation(project(":common"))
    implementation("org.springframework.boot:spring-boot-starter")
    implementation("io.grpc:grpc-netty-shaded:1.54.0")
    implementation("io.grpc:grpc-protobuf:1.54.0")
    implementation("io.grpc:grpc-stub:1.54.0")
}
