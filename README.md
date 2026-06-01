<h1 align="center">📦 sing-box-config</h1>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/python-3.12+-89b4fa?style=for-the-badge&logo=python&logoColor=11111b">
    <source media="(prefers-color-scheme: light)" srcset="https://img.shields.io/badge/python-3.12+-4c7a5d?style=for-the-badge&logo=python&logoColor=ffffff">
    <img alt="Python" src="https://img.shields.io/badge/python-3.12+-89b4fa?style=for-the-badge&logo=python&logoColor=11111b">
  </picture>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/sing--box-1.13+-a6e3a1?style=for-the-badge&logo=go&logoColor=11111b">
    <source media="(prefers-color-scheme: light)" srcset="https://img.shields.io/badge/sing--box-1.13+-2ca5e0?style=for-the-badge&logo=go&logoColor=ffffff">
    <img alt="sing-box" src="https://img.shields.io/badge/sing--box-1.13+-a6e3a1?style=for-the-badge&logo=go&logoColor=11111b">
  </picture>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/built__with-uv-f9e2af?style=for-the-badge&logo=fastapi&logoColor=11111b">
    <source media="(prefers-color-scheme: light)" srcset="https://img.shields.io/badge/built__with-uv-de5d83?style=for-the-badge&logo=fastapi&logoColor=ffffff">
    <img alt="uv" src="https://img.shields.io/badge/built__with-uv-f9e2af?style=for-the-badge&logo=fastapi&logoColor=11111b">
  </picture>
</p>

<p align="center">
  A lightweight, high-performance CLI toolkit for managing <strong>sing-box</strong> configurations — from VLESS URL parsing and JSON templating to binary profile packing (.bpf), rule-set compilation, and live system telemetry.
</p>

---

## ⚡ Key Features

- 🚀 **VLESS → JSON Generator:** Parse standard VLESS share links and inject parameters into customizable JSON templates with automatic UUID, SNI, Reality, WebSocket, and gRPC field mapping.
- 📦 **Binary Profile Packer:** Encode JSON configurations into compressed `.bpf` profiles (compatible with sing-box GUI clients) supporting local, remote, and iCloud storage types.
- 🔧 **Rule-Set Compiler:** Batch-compile JSON rule-sets into binary `.srs` format using the native sing-box core engine.
- 📊 **Live Telemetry Monitor:** Real-time visualization of active `sing-box` processes (CPU/RAM) alongside system-wide resource utilization graphs via `plotext`.
- 🎨 **Catppuccin-Inspired UI:** Rich, color-coded terminal output with interactive prompts, Tab autocompletion, and command history powered by `prompt-toolkit` and `rich`.
- 🌍 **Asset Fetching:** One-command download of essential geoip/geosite databases and precompiled antizapret rule-sets.

---

## 📐 Project Structure

- `cli/main.py`: Entrypoint and interactive REPL shell manager.
- `cli/commands.py`: Logic for generation, packing, compilation, and monitoring.
- `cli/models.py`: Strictly typed Pydantic models for VLESS URI parsing and profile structures.
- `cli/utils.py`: Core utilities for binary execution, JSON templating, and custom binary serialization.

---

## 🚀 Setup & Usage

### 1. Requirements
- Python 3.12+
- `uv` package manager

### 2. Installation
```bash
git clone https://github.com/d43m0n4rch7/sing-box-config
cd sing-box-config
uv sync
```
### 3. Execution
Invoke the CLI via the installed script:
```bash
# Launch interactive REPL
sbc

# Run single command
sing-box-config [command]
```

Features:
- Tab‑based autocompletion
- Persistent command history (`~/.sbc_history`)
- Catppuccin‑styled output

**Example session:**
```text
sbc ❯ config generate
✨ Interactive Configuration Wizard
  Enter VLESS URL: vless://abc123@example.com:443?security=reality&pbk=...
  Select template: default.json
✔ Configuration saved: my_server.json
```

### CLI Mode (non‑interactive)

```bash
sbc config generate "vless://..." -t templates/default.json -o output/myconfig.json
sbc rules compile -d ./rules -o ./rules/srs
sbc other fetch-assets -o ./antizapret
sbc other monitor
```

---

## 🧩 Command Reference

| Group     | Command          | Description                                                                 |
|-----------|------------------|-----------------------------------------------------------------------------|
| `config`  | `generate`       | Generate JSON config from VLESS URL + template (interactive or CLI)        |
|           | `format`         | Format JSON files in `./generate` using `sing-box format -w`               |
|           | `pack`           | Pack JSON config into binary `.bpf` profile (local/remote/iCloud)          |
| `rules`   | `compile`        | Compile JSON rule-sets from `./rules` into `.srs` binaries (auto-formats)  |
| `other`   | `fetch-assets`   | Download `geoip.db`, `geosite.db`, `antizapret.srs`                         |
|           | `monitor`        | Real-time telemetry: active sing-box processes + CPU/RAM graph             |

> 💡 Directories (`templates/`, `generate/`, `pack/`, `rules/`, `srs/`) are auto-created in the project root.

---

## 🔧 Configuration Details

### VLESS URL Parsing

Supported URI format:

```text
vless://<uuid>@<server>:<port>?security=reality&pbk=<public_key>&sni=<sni>&flow=xtls-rprx-vision&type=ws&path=/ws&host=example.com#ProfileName
```

Parsed fields are mapped into `VlessParams` (Pydantic model) and injected into the first `outbound` with `"type": "vless"`.

### Template Structure

Your JSON template must contain at least one `vless` outbound:

```json
{
  "outbounds": [
    {
      "type": "vless",
      "server": "",
      "server_port": 0,
      "uuid": "",
      "flow": "",
      "tls": {
        "enabled": true,
        "server_name": "",
        "utls": { "fingerprint": "chrome" }
      }
    }
  ]
}
```

### Binary Profile Format (`.bpf`)

The packer produces a gzip‑compressed binary:

```text
[version: byte][count: byte][gzipped payload]
  └── payload: [name: uvarint+string][type: int32 big-endian][config: uvarint+string][remote_path (optional)]
```

Compatible with sing-box GUI applications that import `.bpf` profiles.

---

## 📊 Telemetry Monitor Example

```bash
sbc other monitor
```

Output:

```text
📊 Sing-box Core & System Telemetry

✔ Active sing-box core(s) detected:
  • PID: 12345 | CPU: 1.2% | RAM: 24 MB

📈 Resource Utilization Grid:

    100 ─┬────────────────────────────────────
         │  CPU %  ██▌
    80  ─┤  RAM %  ██████▌
         │
       ... [live plotext graph]
```

---

## 🔍 Troubleshooting

### 💡 `sing-box` binary not found
- **Root Cause:** The `sing-box` or `sing-box-beta` executable is not available in your system `PATH`, or the `sing-box-bin` package failed to install correctly.
- **Solution:** Ensure `sing-box` is installed and accessible via `which sing-box`. Alternatively, run `pip install sing-box-bin` to fetch the binary automatically, or specify the full path to the binary in your environment.

### 💡 VLESS parsing fails with "Invalid URL format"
- **Root Cause:** The provided URL does not start with the required `vless://` scheme, or the URL structure is malformed (missing UUID, server, or port).
- **Solution:** Verify that the URL begins with `vless://` and follows the standard format: `vless://<uuid>@<server>:<port>?params#name`. Unknown or exotic parameters are safely ignored and stored in `all_params` without breaking parsing.

### 💡 `.bpf` file doesn't import into GUI client
- **Root Cause:** The profile type (`local`/`remote`/`icloud`) does not match what the target GUI application expects, or the binary payload was corrupted during packing.
- **Solution:** Use the `-t local` flag explicitly when packing: `sbc config pack config.json -t local`. Ensure the input JSON is valid and was generated or formatted by `sbc config generate` or `sbc config format`.

### 💡 JSON template error: "root element must be an object"
- **Root Cause:** The template file contains a JSON array at the root level instead of a dictionary (object). sing-box configurations require a top-level object `{ ... }`.
- **Solution:** Wrap your configuration in curly braces `{ }`. If your template is an array of outbounds, place it inside an `"outbounds"` key within an object.

### 💡 `sbc other monitor` shows no active sing-box processes
- **Root Cause:** No `sing-box` instance is currently running on the system, or the process name does not contain the string "sing-box" (e.g., custom renamed binary).
- **Solution:** Start `sing-box` first (e.g., `sing-box run -c config.json`). If using a custom binary name, modify the process detection logic in `commands.py` or temporarily rename your binary to include "sing-box".

---

## 📄 License

This software is distributed under the terms of the [MIT License](LICENSE). Feel free to inspect, refactor, or scale the repository infrastructure globally.

---

<p align="center">
  Built with 🧠 and strict typing — for the modern proxy toolchain.
</p>