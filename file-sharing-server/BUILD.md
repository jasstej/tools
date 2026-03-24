# Building Executables

This guide explains how to build standalone executables for File Sharing Server on Linux and Windows.

## Prerequisites

### For All Platforms
- Python 3.9+ installed
- Git (for cloning the repository)

### System-Specific

#### Linux/macOS
```bash
# Install dependencies
pip install -r requirements-dev.txt

# Or manually install PyInstaller
pip install pyinstaller>=6.0
```

#### Windows
```cmd
# Install dependencies
pip install -r requirements-dev.txt

# Or manually install PyInstaller
pip install pyinstaller>=6.0
```

## Building Executables

### Linux

1. **Clone/prepare the repository:**
   ```bash
   cd file-sharing-server
   ```

2. **Run the build script:**
   ```bash
   bash build_linux.sh
   ```

3. **The executable will be created at:**
   ```
   dist/file-sharing-server/file-sharing-server
   ```

4. **Run the executable:**
   ```bash
   ./dist/file-sharing-server/file-sharing-server share /path/to/folder
   ```

### Windows

1. **Prepare the repository:**
   ```cmd
   cd file-sharing-server
   ```

2. **Run the build script:**
   ```cmd
   build_windows.bat
   ```

3. **The executable will be created at:**
   ```
   dist\file-sharing-server\file-sharing-server.exe
   ```

4. **Run the executable:**
   ```cmd
   dist\file-sharing-server\file-sharing-server.exe share C:\path\to\folder
   ```

## Manual Build Process

If the build scripts don't work, you can build manually:

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Generate spec file (already included)
# pyinstaller --onedir file_sharing_server/__main__.py --name file-sharing-server

# Build using existing spec
pyinstaller file_sharing_server.spec --clean

# Clean up build artifacts
rm -rf build *.spec
```

## Build Customization

### One-File Executable (Larger, Single File)

Edit `file_sharing_server.spec` and change `onedir` to `onefile`:

```python
# In the file_sharing_server.spec:
# Change to generate a single executable file instead of directory
exe = EXE(
    # ...
    # This already creates a one-dir executable
    # To create one-file, use:
    # exe = EXE(..., onefile=True, ...)
)
```

Then rebuild with `pyinstaller file_sharing_server.spec`

### Platform-Specific Optimization

#### Linux
```bash
# Build with optimizations
pyinstaller file_sharing_server.spec --clean --optimize=2
```

#### Windows
```cmd
REM Build with optimizations
pyinstaller file_sharing_server.spec --clean --optimize=2
```

## Output Structure

### Linux
```
dist/file-sharing-server/
├── file-sharing-server          # Main executable
├── file_sharing_server/         # Package files
│   ├── ui/
│   │   └── index.html
│   └── *.py
├── libssl.so.1.1 (if needed)
└── other dependencies
```

### Windows
```
dist\file-sharing-server\
├── file-sharing-server.exe      # Main executable
├── file_sharing_server\         # Package files
│   ├── ui\
│   │   └── index.html
│   └── *.py
├── python*.dll
└── other dependencies
```

## Usage After Building

### First Time Setup
```bash
# Share a folder (generates tokens and certificates automatically)
./dist/file-sharing-server/file-sharing-server share ~/Documents

# Or with HTTPS
./dist/file-sharing-server/file-sharing-server share ~/Documents --https

# Or disable rate limiting
./dist/file-sharing-server/file-sharing-server share ~/Documents --no-rate-limit
```

### List Shares
```bash
./dist/file-sharing-server/file-sharing-server list
```

### View Status
```bash
./dist/file-sharing-server/file-sharing-server status
```

## Troubleshooting

### "Module not found" errors
```bash
# Ensure all dependencies are installed
pip install -r requirements.txt
pip install colorama  # Required

# For HTTPS support (optional)
pip install cryptography
```

### Build fails on Windows
- Ensure Python is added to PATH
- Use `py` instead of `python` if needed: `py -m pip install ...`
- Run command prompt as Administrator

### Version conflicts
```bash
# Clear PyInstaller cache
rm -rf build/
rm -rf dist/
rm -rf *.spec

# Rebuild from scratch
pyinstaller file_sharing_server.spec
```

### Antivirus/Gatekeeper warnings
- PyInstaller executables may trigger warnings on first run
- This is normal - the executable is safe, it's just a bundled Python application
- Allow it through your antivirus/gatekeeper

## Distribution

### Creating Release Packages

```bash
# Linux - Create tarball
cd dist
tar czf file-sharing-server-linux-x64.tar.gz file-sharing-server/
sha256sum file-sharing-server-linux-x64.tar.gz > file-sharing-server-linux-x64.tar.gz.sha256

# Windows - Create ZIP
powershell Compress-Archive -Path dist\file-sharing-server `
  -DestinationPath file-sharing-server-windows-x64.zip
(Get-FileHash file-sharing-server-windows-x64.zip).Hash | Out-File file-sharing-server-windows-x64.zip.sha256
```

## Next Steps

For cross-platform building:
- **Docker:** Use Docker images with different Python/OS combinations
- **GitHub Actions:** Automate builds and create releases
- **CI/CD:** Set up automatic executable generation on each commit

## Support

For build issues:
- Check PyInstaller documentation: https://pyinstaller.org/
- Verify Python version: `python --version` (requires 3.9+)
- Check dependencies: `pip list | grep -E "PyInstaller|colorama|cryptography"`
