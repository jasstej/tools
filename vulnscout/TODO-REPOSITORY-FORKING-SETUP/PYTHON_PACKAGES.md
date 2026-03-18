# VulnScout Python Packages for Forking

List of Python packages installed by the install script. These can be forked to your own repository for reliable access and custom modifications.

## Packages Overview

| Package | Purpose | Repository | Stars | Notes |
|---------|---------|-----------|-------|-------|
| **LinkFinder** | Discover endpoints/parameters from JavaScript code | https://github.com/GerbenJavado/LinkFinder | JS endpoint discovery | Helps find hidden API endpoints |
| **commix** | Command Injection Testing Tool | https://github.com/commixproject/commix | OS command injection | Automated exploitation of commix via GET/POST/COOKIE |
| **dotdotpwn** | Directory Traversal Scanner | https://github.com/wireghoul/dotdotpwn | Path traversal testing | Cross-platform directory traversal vulnerability tester |
| **wafw00f** | WAF Fingerprinting Tool | https://github.com/EnableSecurity/wafw00f | WAF detection | Identifies and fingerprints web application firewalls |
| **paramspider** | Parameter Discovery Spider | https://github.com/devanshbatham/ParamSpider | Parameter discovery | Finds parameters for common web applications |
| **ghauri** | SQL Injection Vulnerability Scanner | https://github.com/r0ot h3r0/ghauri | SQLi testing | Automated SQL injection vulnerability detection |
| **jwt-tool** | JWT (JSON Web Token) Testing | https://github.com/ticarpi/jwt_tool | JWT security | Toolkit for testing jwtAuthentication implementation |
| **arjun** | HTTP Parameter Fuzzer | https://github.com/s0md3v/Arjun | Parameter fuzzing | Finds valid parameter names for web applications |
| **SubDomainizer** | Subdomain Discovery from JS | https://github.com/nsonaniya2010/SubDomainizer | Subdomain enumeration | Extracts subdomains from JavaScript files |
| **anew** | Unique Finding Manager | https://github.com/tomnomnom/anew | Output filtering | Keeps track of unique results across scans |

## Installation Location

- **Virtual Environment Path**: `~/.vulnscout-env`
- **Activation Command**: `source ~/.vulnscout-env/bin/activate`
- **Deactivation Command**: `deactivate`

## Forking Strategy

### High Priority (Core Tools)
- **commix** - Critical for command injection testing
- **ghauri** - Important for SQLi testing
- **wafw00f** - Essential for WAF detection
- **LinkFinder** - Valuable for endpoint discovery

### Medium Priority (Useful Utilities)
- **paramspider** - Good for parameter discovery
- **arjun** - Useful fuzzing tool
- **SubDomainizer** - Helps with subdomain enumeration

### Optional (Support Tools)
- **jwt-tool** - For JWT-specific testing
- **dotdotpwn** - Specific to path traversal
- **anew** - Output filtering utility

## Forking Checklist

- [ ] Create organization repos for each package
- [ ] Mirror repositories
- [ ] Add CI/CD for updates (GitHub Actions)
- [ ] Document any custom modifications
- [ ] Update install script to use forked repositories
- [ ] Setup automated sync from upstream (optional)

## Custom Installation from Forked Repos

Update the `install_python_tools()` function to install from your forked repos:

```bash
pip install git+https://github.com/YOUR_ORG/LinkFinder.git
pip install git+https://github.com/YOUR_ORG/commix.git
# ... etc
```

Or use a `requirements.txt`:

```
git+https://github.com/YOUR_ORG/LinkFinder.git
git+https://github.com/YOUR_ORG/commix.git
git+https://github.com/YOUR_ORG/dotdotpwn.git
git+https://github.com/YOUR_ORG/wafw00f.git
git+https://github.com/YOUR_ORG/paramspider.git
git+https://github.com/YOUR_ORG/ghauri.git
git+https://github.com/YOUR_ORG/jwt-tool.git
git+https://github.com/YOUR_ORG/arjun.git
git+https://github.com/YOUR_ORG/SubDomainizer.git
git+https://github.com/YOUR_ORG/anew.git
```

Then replace the install section with:
```bash
pip install -r requirements.txt
```
