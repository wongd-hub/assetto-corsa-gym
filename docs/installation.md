# Installation

Complete installation guide for AC Bridge.

## System Requirements

- **OS:** Windows 10/11 (64-bit)
- **Python:** 3.11 or higher
- **Game:** Assetto Corsa (original, not Competizione)
- **Memory:** 2GB+ RAM
- **Disk:** 500MB for dependencies

## Step 1: Install Python

### Option A: Microsoft Store (Recommended)

```bash
# Search "Python 3.11" in Microsoft Store and install
```

### Option B: python.org

Download from [python.org/downloads](https://www.python.org/downloads/)

Verify installation:

```bash
python --version
# Should show Python 3.11.x or higher
```

## Step 2: Install uv (Optional but Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer:

```powershell
# PowerShell (as Administrator)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal, then verify:

```bash
uv --version
```

## Step 3: Install vJoy

vJoy is required for sending control inputs to AC.

1. Download [vJoy 2.1.9](http://vjoystick.sourceforge.net/site/index.php/download-a-install/download)
2. Run installer
3. **Configure device 1:**
   - Open "Configure vJoy" from Start Menu
   - Select "Device 1"
   - Enable axes: X, Y, Z, RZ
   - Enable 12 buttons
   - Click "Apply"

Verify in Windows Device Manager:
- Devices and Printers → vJoy Device should appear

## Step 4: Install AC Bridge

### Clone Repository

```bash
git clone https://github.com/wongd-hub/assetto-corsa-gym.git
cd assetto-corsa-gym
```

### Install Dependencies

With uv (recommended):

```bash
uv sync
uv pip install -e .
```

With pip:

```bash
pip install -e .
```

## Step 5: Verify Installation

### Test Telemetry

Start Assetto Corsa, enter a session, then:

```bash
uv run ac-bridge test-telemetry --hz 10
```

You should see live telemetry output:

```
Speed: 145 km/h | RPM: 5420 | Gear: 3 | Throttle: 85%
```

### Test vJoy Control

```bash
uv run ac-bridge test-control
```

Interactive menu should appear. Test each axis to verify vJoy is working.

### Run Smoke Test

Combined test of telemetry + control:

```bash
uv run ac-bridge smoke-test
```

## Step 6: Configure AC Controls

Map vJoy in Assetto Corsa:

1. Launch AC → Options → Controls
2. **Change device to "vJoy Device"**
3. Map axes:
   - Steering → vJoy X axis
   - Throttle → vJoy Y axis
   - Brake → vJoy Z axis
   - Clutch → vJoy RZ axis (optional)
4. Map buttons (optional):
   - Button 7 → Restart session
   - Button 9 → Start race
5. **Save and test** - drive around to verify controls work

## Troubleshooting

### Python not found

```bash
# Check Python is in PATH
python --version

# If not found, add to PATH:
# Settings → System → About → Advanced system settings
# → Environment Variables → Path → Add Python install dir
```

### uv not recognized

```bash
# Restart terminal after installing uv
# If still not working, add to PATH:
%USERPROFILE%\.cargo\bin
```

### vJoy device not found

```python
# Check if vJoy is installed
import pyvjoy
device = pyvjoy.VJoyDevice(1)  # Should not raise error
```

If error:
1. Reinstall vJoy
2. Configure device 1 in vJoy Configure tool
3. Reboot Windows

### ModuleNotFoundError

```bash
# Make sure you installed in editable mode
cd assetto-corsa-gym
uv pip install -e .

# Or with pip
pip install -e .
```

### AC telemetry not available

Make sure:
1. AC is running (not just launcher)
2. You're in a session (practice/race, not main menu)
3. Shared memory is enabled (usually enabled by default)

### vJoy controls not working in AC

1. Check device in Windows Device Manager
2. Test vJoy with `uv run ac-bridge test-control`
3. Re-map controls in AC (sometimes AC resets mappings)
4. Make sure **no other controller is active** in AC

## Optional: Development Setup

For contributing or modifying AC Bridge:

```bash
# Install dev dependencies
uv sync --dev

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install

# Run tests
pytest

# Build docs locally
uv run mkdocs serve
```

## Next Steps

- ✅ Installation complete!
- 📖 [Quick Start Guide](getting-started.md)
- 🚀 [Build your first integration](getting-started.md#your-first-integration)
- 📚 [API Reference](api/overview.md)

## Updating

To update to the latest version:

```bash
cd assetto-corsa-gym
git pull
uv sync  # or pip install -e .
```

Check the [release notes](https://github.com/wongd-hub/assetto-corsa-gym/releases) for breaking changes.

