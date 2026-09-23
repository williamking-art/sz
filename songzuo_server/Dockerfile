# 宋祚后端（Rust · axum）容器镜像
#
# 两阶段构建：builder 编出 release 二进制，运行阶段只带二进制与证书，镜像小、启动快。
#
# 与 src/main.rs 的运行约定严格一致：
#   - 优先读平台注入的 PORT，并强制绑 0.0.0.0（readiness probe 只探服务端口，
#     绑 127.0.0.1 会直接判定部署失败）
#   - 因此本镜像**故意不设 SONGZUO_ADDR**：它的优先级高于 PORT，一旦设了就会
#     覆盖平台端口，导致探针端口对不上、部署失败
#
# 构建：
#   docker build -t songzuo_server:0.1.0 .
# 运行：
#   docker run --rm -p 8080:8080 -e PORT=8080 songzuo_server:0.1.0
#   curl -s http://127.0.0.1:8080/healthz

FROM rust:1-slim-bookworm AS builder

# slim 变体不带 C 工具链，Rust 链接阶段需要 cc 与 libc 头文件
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libc6-dev \
 && rm -rf /var/lib/apt/lists/*

# crates.io 直连在国内构建机上容易超时，默认走 rsproxy 稀疏索引。
# 传 --build-arg CARGO_REGISTRY= 可关闭（改用官方源）。
ARG CARGO_REGISTRY=sparse+https://rsproxy.cn/index/
RUN if [ -n "$CARGO_REGISTRY" ]; then \
      printf '[source.crates-io]\nreplace-with = "mirror"\n[source.mirror]\nregistry = "%s"\n' \
        "$CARGO_REGISTRY" > "$CARGO_HOME/config.toml"; \
    fi

WORKDIR /build

# 先只拷依赖清单做一次「空壳编译」，把依赖层缓存住：
# 之后只改 src/ 不会触发依赖重编，镜像重建从分钟级降到秒级。
COPY Cargo.toml Cargo.lock ./
RUN mkdir -p src && echo 'fn main() {}' > src/main.rs \
 && cargo build --release \
 && rm -rf src

COPY src ./src
RUN touch src/main.rs && cargo build --release


FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /data/saves

COPY --from=builder /build/target/release/songzuo_server /usr/local/bin/songzuo_server

# 存档目录：容器内为临时盘，实例重启即失。要持久化请挂 CFS 卷到 /data/saves。
ENV SONGZUO_SAVE_DIR=/data/saves
EXPOSE 8080

CMD ["songzuo_server"]
