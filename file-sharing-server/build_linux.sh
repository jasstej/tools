#!/bin/bash
# Build executable for Linux

echo "Building File Sharing Server for Linux..."
python -m PyInstaller file_sharing_server.spec --clean

if [ $? -eq 0 ]; then
    echo "✓ Build successful!"
    echo "Executable location: dist/file-sharing-server"
    echo ""
    echo "Run with: ./dist/file-sharing-server/file-sharing-server share /path/to/folder"
else
    echo "✗ Build failed"
    exit 1
fi
