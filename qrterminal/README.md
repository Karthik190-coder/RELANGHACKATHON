# qrterminal — C# Implementation

QR code generator for the terminal. Faithful C# port of the Go reference implementation.

| Field | Value |
|-------|-------|
| **Type** | Easy |
| **Score** | 100 |
| **Reference** | Go |
| **Implementation** | C# (.NET 8) |

## Prerequisites

### For building/running via dotnet CLI (Ubuntu 24.04 / Linux):
You can install the .NET 8 SDK directly from the official Ubuntu package manager:
```bash
sudo apt-get update
sudo apt-get install -y dotnet-sdk-8.0
```

### For running the self-contained binary (no runtime required):
The binary in [target/publish/QrTerminal.Cli](file:///k:/Dev/RELANGHACKATHON/qrterminal/target/publish/QrTerminal.Cli) is a self-contained single-file executable built for `linux-x64`. It has the .NET runtime bundled directly inside it and does not require the .NET SDK or runtime to be installed on Ubuntu 24.04.
You may only need to make it executable:
```bash
chmod +x target/publish/QrTerminal.Cli
```

## Build

```bash
dotnet build target/QrTerminal.Cli/QrTerminal.Cli.csproj -c Release
```

## Run

```bash
# Using dotnet run
dotnet run --project target/QrTerminal.Cli -- -l L "https://example.com"

# Or using the self-contained binary (Linux)
target/publish/QrTerminal.Cli "https://example.com"
```

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `-l L/M/H` | `L` | Error correction level |
| `-q N` | `2` | Quiet zone border size |
| `-v` | `false` | Verbose/debug output |

## Validate

Output hashes match Go reference exactly (SHA256 verified).

```bash
# Compare hashes (PowerShell)
$goOut  = go run ./source/cmd/qrterminal -l L "test"
$csOut  = dotnet run --project target/QrTerminal.Cli -- -l L "test"
# Must be equal
$goOut -eq $csOut
```

## Submit

```bash
# Windows
relang "dotnet run --project qrterminal/target/QrTerminal.Cli --"

# Or with self-contained Linux binary
relang "qrterminal/target/publish/QrTerminal.Cli"
```
