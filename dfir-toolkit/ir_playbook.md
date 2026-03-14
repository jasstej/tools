# Incident Response Playbook
## Digital Forensics & Incident Response (DFIR) Operational Guide

**Version:** 2.1
**Classification:** Internal Use — Security Operations
**Owner:** Security Operations Center (SOC)
**Last Updated:** 2024-01-15

---

## Overview

This playbook defines the structured, repeatable process for responding to cybersecurity incidents within the organisation. It covers the full lifecycle from preparation through post-incident review and applies to all confirmed or suspected security events affecting company systems, data, or infrastructure.

**Scope:** All production systems, user endpoints, cloud environments, and third-party integrations.

**Activation Criteria:** This playbook activates upon receipt of any Severity 1-3 security alert from SIEM, EDR, or analyst discovery.

---

## Phase 1: Preparation

### Objectives
- Ensure IR team is equipped, trained, and ready to respond at all times
- Maintain up-to-date tools, credentials, and documentation
- Establish communication channels before an incident occurs

### Tasks Checklist

- [ ] Review and update Incident Response Policy annually
- [ ] Maintain current emergency contact list (IR team, legal, PR, executives, law enforcement liaisons)
- [ ] Verify forensic toolkit is current: Volatility, Autopsy, Wireshark, KAPE, Velociraptor
- [ ] Confirm access credentials for all critical systems are stored in PAM vault
- [ ] Test out-of-band communication channel (Signal group, satellite phone for critical incidents)
- [ ] Verify evidence storage systems have sufficient capacity (>2 TB available)
- [ ] Schedule quarterly IR tabletop exercise
- [ ] Confirm legal hold procedures are documented and approved
- [ ] Maintain threat intelligence feeds: ISAC, CISA advisories, vendor bulletins
- [ ] Verify backup integrity for all Tier 1 systems
- [ ] Confirm SIEM correlation rules are tuned and producing actionable alerts
- [ ] Document network topology and asset inventory — reviewed quarterly

### Tools Used
- Password/PAM vault (CyberArk, HashiCorp Vault)
- EDR platform (CrowdStrike, SentinelOne, Defender for Endpoint)
- SIEM (Splunk, Elastic SIEM, IBM QRadar)
- Asset inventory (ServiceNow CMDB, Lansweeper)
- Communication platform with E2E encryption

### Outputs / Deliverables
- Signed IR Policy document
- Updated contact escalation tree
- Forensic toolkit inventory sheet
- Quarterly readiness assessment report

---

## Phase 2: Identification

### Objectives
- Determine whether a security event constitutes a confirmed incident
- Scope the incident: systems affected, data involved, attack vector
- Assign severity rating and trigger appropriate notifications

### Tasks Checklist

- [ ] Review initial alert details in SIEM / ticketing system
- [ ] Correlate alert against threat intelligence to assess credibility
- [ ] Identify affected assets: hostnames, IPs, user accounts
- [ ] Determine initial attack vector: phishing, exploit, credential abuse, insider
- [ ] Assign severity rating (see matrix below)
- [ ] Open incident ticket with case ID, timestamp, initial findings
- [ ] Notify incident commander and on-call analyst
- [ ] Notify CISO if Severity 1 or 2
- [ ] Assess regulatory notification requirements (GDPR 72-hour rule, HIPAA, PCI DSS)
- [ ] Establish incident bridge call / war room
- [ ] Preserve initial evidence: screenshots, log exports, SIEM queries

### Severity Rating Matrix

| Severity | Criteria | Response SLA |
|---|---|---|
| SEV-1 | Active breach, data exfiltration confirmed, ransomware spreading | Immediate (< 15 min) |
| SEV-2 | Suspected breach, lateral movement detected, privileged account compromise | < 1 hour |
| SEV-3 | Malware on isolated host, phishing with no payload execution | < 4 hours |
| SEV-4 | Policy violation, low-risk alert, failed login attempts | < 24 hours |

### Tools Used
- SIEM query console
- Threat intelligence platform (ThreatConnect, MISP)
- Ticketing system (Jira, ServiceNow)
- Network topology maps
- Asset inventory

### Outputs / Deliverables
- Incident ticket with initial assessment
- Severity classification
- Affected asset list
- Notification log (who was told what and when)

---

## Phase 3: Containment

### Objectives
- Stop the spread of the incident to unaffected systems
- Preserve evidence while preventing further damage
- Maintain business continuity where possible

### Tasks Checklist

**Short-Term Containment (immediate)**
- [ ] Isolate affected hosts from network (EDR quarantine or manual VLAN segregation)
- [ ] Block malicious IPs and domains at perimeter firewall and DNS sinkhole
- [ ] Disable compromised user accounts in Active Directory / IdP
- [ ] Revoke active sessions and tokens for affected accounts
- [ ] Capture memory dump of affected systems BEFORE any remediation
- [ ] Take forensic disk image of affected systems (write-blocker required)

**Long-Term Containment (within 4 hours for SEV-1)**
- [ ] Snapshot affected VMs in current state for forensic analysis
- [ ] Preserve all relevant log sources: SIEM, firewall, EDR, AD, DNS, proxy
- [ ] Implement additional monitoring on related systems
- [ ] Communicate containment actions to change management
- [ ] Establish clean network segment for business continuity if needed
- [ ] Notify affected business units of service disruption with ETA

### Tools Used
- EDR console (quarantine/isolation)
- Firewall management console
- Active Directory / Azure AD admin tools
- Forensic imaging tools: dd, FTK Imager, KAPE
- Memory capture: WinPmem, LiME (Linux Memory Extractor)
- Virtualization console (vSphere, AWS Console)

### Outputs / Deliverables
- Containment action log with timestamps
- Forensic images with hash verification (SHA-256)
- Chain of custody forms for all evidence
- Business impact assessment

---

## Phase 4: Eradication

### Objectives
- Remove all traces of the threat actor from the environment
- Address the root cause and close the attack vector
- Validate complete removal before proceeding to recovery

### Tasks Checklist

- [ ] Identify all malware artifacts: files, registry keys, scheduled tasks, services
- [ ] Run full AV/EDR scan on all systems in the affected network segment
- [ ] Remove identified malware using EDR or manual forensic removal
- [ ] Identify and patch the exploited vulnerability (CVE reference if known)
- [ ] Reset passwords for all affected accounts and service accounts
- [ ] Rotate all API keys, certificates, and secrets potentially exposed
- [ ] Remove attacker persistence mechanisms: backdoors, web shells, cron jobs
- [ ] Audit and remove unauthorised user accounts or privilege escalations
- [ ] Validate registry and startup locations are clean
- [ ] Check for DNS hijacking or BGP route modifications
- [ ] Review and harden configuration of affected services
- [ ] Rescan with multiple tools to confirm clean state

### Tools Used
- EDR remediation console
- Vulnerability scanner (Tenable Nessus, Qualys)
- Password reset utilities
- Secrets rotation tools (HashiCorp Vault, AWS Secrets Manager)
- Registry analysis (Autoruns, RegRipper)
- File integrity monitoring

### Outputs / Deliverables
- Eradication completion report
- Patched vulnerability list with CVE references
- Credential rotation log
- Clean bill of health scan results

---

## Phase 5: Recovery

### Objectives
- Restore affected systems to normal operations safely
- Verify integrity of restored systems before returning to production
- Monitor closely for signs of re-infection

### Tasks Checklist

- [ ] Identify clean restore points: last known good backup predating incident
- [ ] Verify backup integrity before restoration (hash comparison)
- [ ] Restore systems from verified clean backups in isolated environment first
- [ ] Apply all security patches to restored systems before rejoining production
- [ ] Conduct application-level smoke testing after restoration
- [ ] Restore user access with MFA enforcement on re-enabled accounts
- [ ] Implement enhanced monitoring: increased log verbosity, EDR telemetry
- [ ] Set up tripwires and canary tokens on previously compromised paths
- [ ] Phased return to production: test environment first, then staging, then prod
- [ ] Monitor for 30 days post-recovery for signs of re-compromise
- [ ] Close incident ticket with recovery timestamp
- [ ] Communicate system restoration to affected business units

### Tools Used
- Backup/restore platform (Veeam, Commvault, AWS Backup)
- Configuration management (Ansible, Chef, Puppet)
- File integrity monitoring (Tripwire, AIDE)
- Canary token platform (canarytokens.org)
- MFA platform (Duo, Okta, Azure MFA)

### Outputs / Deliverables
- Recovery timeline log
- Backup integrity verification report
- Enhanced monitoring plan (30-day window)
- Business unit notification of restoration

---

## Phase 6: Lessons Learned

### Objectives
- Understand the full scope and root cause of the incident
- Improve detection, response, and prevention capabilities
- Document findings for regulatory and legal requirements

### Tasks Checklist

- [ ] Schedule post-mortem within 72 hours of incident closure
- [ ] Prepare timeline of events: first compromise to full containment
- [ ] Document root cause analysis (RCA)
- [ ] Identify detection gaps: why wasn't this caught sooner?
- [ ] Update SIEM correlation rules to detect this attack pattern
- [ ] Update threat hunting queries and IOC watchlists
- [ ] Create or update runbooks for this attack type
- [ ] Conduct targeted security awareness training for affected users
- [ ] Review and update DR/BCP documentation based on lessons
- [ ] Generate metrics report: MTTD, MTTR, financial impact estimate
- [ ] Share sanitised TTPs with ISAC or trusted peer organisations
- [ ] Complete regulatory notifications if not already done

### Tools Used
- Incident documentation platform
- SIEM rule management console
- Threat intelligence platform (IOC ingestion)
- Training platform (KnowBe4, Proofpoint Security Awareness)
- Reporting/BI tools

### Outputs / Deliverables
- Post-mortem report (executive summary + technical detail)
- Updated correlation rules and detection content
- MTTD/MTTR metrics report
- Regulatory notification records
- Updated IR playbook (this document)

---

## Specific Playbooks

### Ransomware Incident Response

**Immediate Actions (first 15 minutes)**
1. Confirm ransomware activity: encrypted files, ransom note, EDR alerts
2. Activate SEV-1 bridge call immediately
3. **Identify kill switch:** Check dropper binary for hardcoded domain (WannaCry style) — do NOT register without legal approval
4. Network isolation: cut affected hosts from network immediately
5. Identify Patient Zero: first encrypted host, earliest EDR alert
6. Check backup systems — isolate them from network immediately to prevent encryption

**Investigation**
- [ ] Identify ransomware family (Ransom.NotPetya, LockBit, BlackCat, etc.)
- [ ] Check ID Ransomware (id-ransomware.malwarehunterteam.com) if safe to do so
- [ ] Determine if data exfiltration occurred BEFORE encryption (double extortion)
- [ ] Search for LOLBins used: certutil, powershell, wmic, mshta
- [ ] Check for lateral movement via SMB, RDP, WMI, PSExec
- [ ] Identify initial access vector: phishing email, exposed RDP, exploit

**Containment (kill chain interruption)**
- [ ] Block C2 domains and IPs at firewall
- [ ] Disable SMBv1 if not already done
- [ ] Isolate all affected network segments
- [ ] Check for scheduled tasks or persistence: `schtasks /query /fo list /v`
- [ ] Investigate domain admin account usage in last 72 hours

**Recovery decision tree:**
1. Backups clean and recent? -> Restore. Do NOT pay ransom.
2. No backups or backups compromised? -> Engage IR retainer, assess decryptor availability.
3. Public decryptor available? -> Use NoMoreRansom.org resources.
4. Nation-state / destructive wiper? -> Engage law enforcement (FBI IC3, CISA).

---

### Data Breach Incident Response

**Scope Determination**
- [ ] Identify what data was accessed: PII, PHI, PCI, IP, credentials
- [ ] Determine data classification levels involved
- [ ] Quantify records affected (exact count for regulatory purposes)
- [ ] Confirm whether data left the environment (DLP alerts, egress logs)

**Evidence Preservation**
- [ ] Preserve DLP logs, proxy logs, CASB logs showing data access
- [ ] Capture web server access logs for exfiltration paths
- [ ] Document all access to affected data repositories in last 30 days
- [ ] Hash and seal all evidence immediately

**Notification Obligations**
- GDPR: notify DPA within 72 hours if high risk to individuals
- HIPAA: notify HHS and individuals within 60 days
- PCI DSS: notify card brands (Visa, Mastercard) and acquirer immediately
- State breach laws: varies by state, typically 30-72 hours

**Legal and Regulatory**
- [ ] Brief General Counsel immediately on SEV-1 breach
- [ ] Do not destroy any evidence (legal hold)
- [ ] Document all decisions and their rationale
- [ ] Engage cyber insurance carrier

---

### Insider Threat Incident Response

**Indicators of Insider Threat**
- Bulk download of files outside business hours
- Access to systems not related to job function
- USB mass storage device activity
- Emails to personal accounts containing attachments
- Recent HR events: resignation, demotion, PIP

**Investigation Approach**
- [ ] Obtain HR records for subject (in coordination with HR and Legal)
- [ ] Review DLP alerts for last 90 days for the user
- [ ] Audit badge access logs: physical location correlation
- [ ] Review email gateway logs for external email forwarding rules
- [ ] Examine cloud storage sync activity (OneDrive, Dropbox, Google Drive)
- [ ] Interview manager and peers (Legal must be present)
- [ ] Preserve all evidence under legal hold before any confrontation

**Key Principle:** All insider threat investigations must be approved by Legal and HR before active investigation. Maintain strict need-to-know.

---

## IOC Collection Template

| Field | Value |
|---|---|
| Case ID | |
| Analyst | |
| Collection Date | |
| **File Indicators** | |
| File hash (MD5) | |
| File hash (SHA-256) | |
| File name | |
| File path | |
| File size (bytes) | |
| Compile timestamp | |
| **Network Indicators** | |
| IP address | |
| Domain / FQDN | |
| URL | |
| User-Agent string | |
| Port | |
| Protocol | |
| **Host Indicators** | |
| Registry key | |
| Scheduled task name | |
| Service name | |
| Mutex name | |
| **Email Indicators** | |
| Sender address | |
| Subject line | |
| Attachment hash | |
| Header anomalies | |

---

## Communication Templates

### Initial Incident Notification (Internal)

> **SUBJECT: [SEV-X] Security Incident — [Brief Description] — [Date]**
>
> Team,
>
> We are investigating a potential security incident. Details are preliminary and subject to change.
>
> - **Incident ID:** [CASE-ID]
> - **Detected At:** [Timestamp UTC]
> - **Severity:** [SEV-1/2/3/4]
> - **Affected Systems:** [List]
> - **Current Status:** Investigation in progress
> - **Next Update:** [Time]
>
> Please stand by for further instructions. Do not discuss this matter outside this channel.
>
> — [Incident Commander]

### Executive Briefing Template

> **SUBJECT: Executive Briefing — Security Incident [CASE-ID]**
>
> **What Happened:** [2-sentence summary]
> **Business Impact:** [Systems affected, downtime, data at risk]
> **What We Are Doing:** [Actions taken]
> **What We Need From You:** [Decisions required, resources needed]
> **Next Update:** [Time]
> **Regulatory Exposure:** [Yes/No — brief explanation]

---

*End of Incident Response Playbook v2.1*
*Next review date: 2025-01-15*
*Approved by: CISO*
