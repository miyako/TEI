# TEI
Local inference engine

### Apple Silicon

```
cargo build --release --features metal --target aarch64-apple-darwin
```

### Intel

```
RUSTFLAGS="-C target-cpu=haswell" cargo build --release --features accelerate --target x86_64-apple-darwin
```

### Windows

```
rustup default stable-x86_64-pc-windows-msvc --force-non-host
rustup override set stable-x86_64-pc-windows-msvc
cargo clean
cargo build --release --target x86_64-pc-windows-msvc
```

> [!WARNING]
> Don't use Visual Studio 2026 (18). Only 2022 (17) is supported.

* clear .cargo/target.toml

```
rustup target add x86_64-pc-windows-msvc
rustup default stable-x86_64-pc-windows-msvc
cargo clean
cargo +stable-x86_64-pc-windows-msvc build --release --target x86_64-pc-windows-msvc
```

or 

```
set CMAKE_GENERATOR=Ninja
cargo build
```

https://huggingface.co/docs/text-embeddings-inference/local_cpu
