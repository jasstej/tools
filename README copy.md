# Security Reconnaissance Workflow

A comprehensive dark-themed HTML guide for performing methodical security reconnaissance and vulnerability assessment on target domains.

## 📋 Overview

This interactive workflow guide provides a structured 10-step process for:
- Subdomain enumeration
- Live host identification
- Web endpoint discovery and crawling
- XSS vulnerability detection
- JavaScript file discovery
- Secret/API key extraction
- API testing and validation
- Vulnerability scanning with Nuclei
- Results analysis and compilation
- Report generation

## 🚀 Usage

1. **Open the HTML file** in your web browser:
   ```
   workflow.html
   ```

2. **Enter your target domain** in the input field (e.g., `example.com`)

3. **Click "Generate Workflow"** or press Enter

4. **Review each step** with pre-customized commands for your domain

5. **Copy commands** using the "Copy" button on each command block

## 🎨 Features

- **Dark Theme Design**: Eye-friendly interface optimized for long work sessions
- **Dynamic Domain Input**: All commands auto-populate with your target domain
- **Copy-to-Clipboard**: Single-click command copying
- **Responsive Layout**: Works on desktop and mobile devices
- **Detailed Descriptions**: Each step includes context and best practices
- **Multiple Methods**: Alternative approaches for different scenarios
- **Notes & Warnings**: Important considerations for each phase

## 📊 Workflow Steps

| Step | Focus | Tools |
|------|-------|-------|
| 1 | Subdomain Discovery | Subfinder, Katana, Wayback Machine |
| 2 | HTTP Probing | httpx, httpx-toolkit |
| 3 | Web Crawling | Katana with historical data |
| 4 | XSS Detection | GFX, XSS-Vibes |
| 5 | JS Discovery | Grep filtering |
| 6 | Secret Scanning | SecretFinder |
| 7 | API Testing | Maps API Scanner |
| 8 | Vuln Scanning | Nuclei |
| 9 | Analysis | Manual review |
| 10 | Reporting | Documentation |

## ⚠️ Important Notes

- **Authorization**: Only test domains you have explicit permission to test
- **Legal Compliance**: Ensure your testing complies with all applicable laws
- **Tool Installation**: Ensure all referenced tools are installed on your system
- **Path Updates**: Update tool paths in commands to match your system configuration
- **False Positives**: Manually verify all findings, especially from automated tools
- **Rate Limiting**: Be mindful of rate limits when crawling and scanning

## 🔧 Customization

You can modify the workflow by editing the `steps` array in the JavaScript section of the HTML file. Add, remove, or modify steps as needed for your specific use case.

## 📝 Common Path Updates Needed

Before running commands, update these paths:
- `/path/to/SecretFinder/SecretFinder.py` → Your actual SecretFinder installation
- `~/pvt-template/` → Your actual Nuclei templates directory
- Any other tool paths specific to your system

## 💡 Tips

- Start with subdomains.txt from Step 1 and follow sequentially
- Use tee command to save output while viewing
- Keep all output files for comprehensive reporting
- Run during off-peak hours to minimize impact
- Document any custom findings or interesting patterns discovered

## 📄 License

Use responsibly. Only test systems you own or have permission to test.

---

**Last Updated**: January 2026
