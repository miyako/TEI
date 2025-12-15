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
