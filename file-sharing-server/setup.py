from setuptools import setup, find_packages
from pathlib import Path

readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text()

setup(
    name="file-sharing-server",
    version="1.0.0",
    description="Simple LAN file sharing server with web UI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Security Tools Team",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=[
        "colorama>=0.4.4",  # Optional, for colored output
    ],
    entry_points={
        "console_scripts": [
            "file-sharing-server=file_sharing_server.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: File Transfer Protocol (HTTP)",
    ],
)
