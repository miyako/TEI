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
cargo build --release --target x86_64-pc-windows-msvc
```
