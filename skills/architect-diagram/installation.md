# Installation

Full installation instructions for the architect-diagram skill on all platforms.

---

## 1. D2 diagram renderer

D2 is required for the D2 engine (`src/generate_d2.py`).

| Platform | Command |
|----------|---------|
| macOS | `brew install d2` |
| Linux | `curl -fsSL https://d2lang.com/install.sh \| sh` |
| Windows | `winget install terrastruct.d2` |

For Windows without winget, download the binary from https://github.com/terrastruct/d2/releases and add it to your PATH.

Verify: `d2 --version`

### Troubleshooting: d2 not in PATH

If `d2` is not found after installation:

- **macOS/Linux**: Ensure `/usr/local/bin` or `~/.local/bin` is in your PATH. The install script prints the install location.
- **Windows**: Add the folder containing `d2.exe` to your system PATH via System Properties > Environment Variables.

---

## 2. Python packages

```bash
pip install pyyaml anthropic diagrams
```

If you are in a virtual environment, activate it first.

If `pip` is not found, use `pip3` or `python3 -m pip install`.

### Troubleshooting: diagrams install fails

The `diagrams` package requires Graphviz (see below). Install Graphviz first, then re-run `pip install diagrams`.

---

## 3. Graphviz

Graphviz is required by the `diagrams` package for the simple diagrams engine.

| Platform | Command |
|----------|---------|
| macOS | `brew install graphviz` |
| Linux (Debian/Ubuntu) | `sudo apt-get install graphviz` |
| Linux (RHEL/CentOS/Amazon) | `sudo yum install graphviz` |
| Linux (Fedora) | `sudo dnf install graphviz` |
| Windows | Download from https://graphviz.org/download/ |

Verify: `dot -V`

### Troubleshooting: graphviz not found

If the `diagrams` package raises `FileNotFoundError: [Errno 2] No such file or directory: 'dot'`:

1. Confirm `dot -V` works in your terminal.
2. If `dot` is installed but not found by Python, the PATH visible to the Python process differs from your shell PATH. Fix:
   - **macOS/Linux**: Add the Graphviz bin directory to your shell profile (`~/.zshrc`, `~/.bashrc`) and restart your terminal.
   - **Windows**: After installing Graphviz, add `C:\Program Files\Graphviz\bin` to system PATH and restart your terminal.

---

## 4. ANTHROPIC_API_KEY

Required only for `src/architect.py` (natural language mode).

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Add to your shell profile (`~/.zshrc`, `~/.bashrc`, or Windows environment variables) to persist across sessions.

To get an API key: https://console.anthropic.com/

---

## Quick verification

After installation, verify everything works:

```bash
# D2 renderer
d2 --version

# Graphviz
dot -V

# Python packages
python3 -c "import yaml, anthropic, diagrams; print('OK')"

# Generate a test diagram (D2)
python3 src/generate_d2.py examples/complex_aws_hybrid.yaml

# Generate a test diagram (simple)
python3 src/generate_diagram.py examples/three_tier_web_app.yaml
```

---

## Platform notes

### macOS

Homebrew is the recommended package manager. Install from https://brew.sh if not already present.

### Linux (Amazon Linux / RHEL)

The `graphviz` package in Amazon Linux 2 via yum may be an older version. It works for the diagrams package. If you need a newer version, consider building from source or using a container.

### Windows

- Python: download from https://python.org. During install, check "Add Python to PATH".
- D2: `winget install terrastruct.d2` or download the `.zip` release from GitHub.
- Graphviz: download the installer from https://graphviz.org/download/ and run it. Make sure to select "Add to PATH" during installation.
- Run commands in PowerShell or Command Prompt. Git Bash also works.
