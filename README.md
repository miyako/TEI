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

```powershell
rustup target add x86_64-pc-windows-msvc
rustup override set stable-x86_64-pc-windows-msvc  
rustup default stable-x86_64-pc-windows-msvc
cargo clean
Import-Module "C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\Tools\Microsoft.VisualStudio.DevShell.dll"
Enter-VsDevShell -VsInstallPath "C:\Program Files\Microsoft Visual Studio\2022\Professional" -SkipAutomaticLocation -DevCmdArguments "-arch=x64 -host_arch=arm64"
$env:CXX = "cl" 
$env:ASM = "nasm" 
cargo +stable-x86_64-pc-windows-msvc build --release --target x86_64-pc-windows-msvc --no-default-features --features http,candle --bin text-embeddings-router
```

* .cargo/config.toml

```toml
[env]
AWS_LC_SYS_NO_C11 = "1"
AWS_LC_SYS_C_STD = "gnu99"

[dependencies]
rustls = { version = "0.23", default-features = false, features = ["std"] }

[target.x86_64-pc-windows-msvc]
linker = "C:\\Program Files\\Microsoft Visual Studio\\2022\\Professional\\VC\\Tools\\MSVC\\14.44.35207\\bin\\Hostx64\\x64\\link.exe"

rustflags = [
  "-C", "target-feature=+crt-static"
]
```

https://huggingface.co/docs/text-embeddings-inference/local_cpu
