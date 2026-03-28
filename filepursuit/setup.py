from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="filepursuit",
    version="1.0.0",
    author="FilePursuit Contributors",
    description="Distributed file search engine for public file indexes",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/filepursuit",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "aiohttp==3.9.0",
        "lxml==4.9.4",
        "colorama==0.4.6",
        "python-dateutil==2.8.2",
        "tabulate==0.9.0",
    ],
    entry_points={
        "console_scripts": [
            "filepursuit=file_pursuit.main:main",
        ],
    },
)
