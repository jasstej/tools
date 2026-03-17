# VulnScout n8n Free-Tier Automation Setup Guide

This guide implements a free-tier n8n automation that turns your VulnScout `example.com` command templates into domain-specific command packs (JSON + Markdown output).

Use this only for authorized testing and legal bug bounty scope.

## What You Will Build

A workflow that:
1. Receives a target domain from Webhook or Manual trigger.
2. Validates and sanitizes the domain.
3. Replaces `example.com` in command templates.
4. Returns structured output as JSON.
5. Optionally sends the command pack to Discord/Slack/email (all possible with free/core nodes).

## Free-Tier Compatible Design

This implementation uses only core nodes:
- `Webhook`
- `Manual Trigger`
- `Set`
- `Code`
- `If`
- `Respond to Webhook`

No paid n8n features are required.

## Prerequisites

1. n8n running (Community Edition or available free cloud workspace).
2. Access to your VulnScout command templates.
3. A public URL for webhook testing (if self-hosted, use reverse proxy or tunnel).

## Workflow Architecture

`Manual Trigger` -> `Set (Test Input)` -> `Code (Normalize Input)` -> `Set (Templates)` -> `Code (Generate Commands)` -> `If (Valid?)`

`If true` -> `Respond to Webhook (Success JSON)`

`If false` -> `Respond to Webhook (Error JSON)`

Also connect:

`Webhook` -> `Code (Normalize Input)`

This lets you test manually and run in API mode.

## Step-by-Step Setup

## 1) Create a New Workflow

1. Open n8n.
2. Click `New workflow`.
3. Name it `VulnScout Command Generator`.

## 2) Add Nodes

Add these nodes in order:

1. `Manual Trigger`
2. `Set` (rename to `Set Test Input`)
3. `Webhook` (rename to `Webhook Input`)
4. `Code` (rename to `Normalize Input`)
5. `Set` (rename to `Command Templates`)
6. `Code` (rename to `Generate Commands`)
7. `If` (rename to `Is Valid Domain`)
8. `Respond to Webhook` (rename to `Success Response`)
9. `Respond to Webhook` (rename to `Error Response`)

## 3) Configure Each Node

### `Set Test Input`

Keep Only Set: `true`

Fields:
- `domain` (string): `example.com`
- `requestedSections` (array or string): `subdomain,urls,sensitive,xss,lfi,cors,wordpress`

### `Webhook Input`

- HTTP Method: `POST`
- Path: `vulnscout/commands`
- Response: `Using Respond to Webhook node`

Expected input body (JSON):

```json
{
  "domain": "target.com",
  "requestedSections": ["subdomain", "urls", "xss"]
}
```

### `Normalize Input` (Code node)

```javascript
const source = $json || {};

const domainRaw = (source.domain || '').toString().trim().toLowerCase();
const cleanedDomain = domainRaw
  .replace(/^https?:\/\//, '')
  .replace(/^\*\./, '')
  .replace(/\/$/, '');

const isValidDomain = /^(?=.{1,253}$)(?!-)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/.test(cleanedDomain);

let requestedSections = source.requestedSections;
if (typeof requestedSections === 'string') {
  requestedSections = requestedSections.split(',').map(s => s.trim()).filter(Boolean);
}
if (!Array.isArray(requestedSections) || requestedSections.length === 0) {
  requestedSections = ['subdomain','urls','sensitive','xss','lfi','cors','wordpress'];
}

return [{
  json: {
    ...source,
    domain: cleanedDomain,
    isValidDomain,
    requestedSections
  }
}];
```

### `Command Templates` (Set node)

Keep Only Set: `false`

Add field `templates` as JSON:

```json
{
  "subdomain": [
    "subfinder -d example.com -all -recursive -o subdomains.txt",
    "assetfinder --subs-only example.com > assetfinder.txt",
    "curl -s \"https://crt.sh/?q=example.com&output=json\" | jq -r '.[].name_value' | sed 's/\\*\\.//g' | sort -u > crtsh.txt",
    "cat subdomains.txt assetfinder.txt crtsh.txt | sort -u > all_subdomains.txt",
    "cat all_subdomains.txt | httpx -silent -o subdomains_alive.txt"
  ],
  "urls": [
    "katana -l subdomains_alive.txt -d 5 -ps -o allurls.txt",
    "cat subdomains_alive.txt | gau | urldedupe >> allurls.txt",
    "cat allurls.txt | grep '=' | sort -u > urls_with_params.txt"
  ],
  "sensitive": [
    "cat allurls.txt | grep -Ei '\\.(txt|log|cache|secret|db|backup|yml|json|gz|rar|zip|config)$'",
    "cat all_subdomains.txt | nuclei -t exposures/ -o sensitive_exposures.txt",
    "cat all_subdomains.txt | grep -Ei '\\.git'"
  ],
  "xss": [
    "cat urls_with_params.txt | gf xss | dalfox pipe -o xss_results.txt",
    "cat urls_with_params.txt | grep -E '=.*' | qsreplace '<script>alert(1)</script>'",
    "cat allurls.txt | grep -Ei '\\.(js)$' | while read url; do python3 linkfinder.py -i \"$url\" -o cli; done"
  ],
  "lfi": [
    "cat urls_with_params.txt | gf lfi",
    "ffuf -u 'https://example.com/?file=FUZZ' -w /usr/share/wordlists/lfi.txt",
    "curl 'https://example.com/?file=../../../../etc/passwd'"
  ],
  "cors": [
    "curl -I -H 'Origin: https://evil.com' https://example.com",
    "python3 corsy.py -i https://example.com",
    "nuclei -u https://example.com -t misconfiguration/cors/"
  ],
  "wordpress": [
    "wpscan --url https://example.com --enumerate u,vp,vt,tt,cb,dbe",
    "whatweb https://example.com",
    "nuclei -u https://example.com -tags wordpress"
  ]
}
```

### `Generate Commands` (Code node)

```javascript
const { domain, isValidDomain, requestedSections, templates } = $json;

if (!isValidDomain) {
  return [{
    json: {
      ok: false,
      domain,
      message: 'Invalid domain format',
      commands: {},
      markdown: ''
    }
  }];
}

const commands = {};
for (const section of requestedSections) {
  if (!templates[section]) continue;
  commands[section] = templates[section].map(cmd =>
    cmd.replace(/example\\.com/g, domain)
  );
}

const lines = [
  `# VulnScout Command Pack`,
  ``,
  `Target: ${domain}`,
  `Generated: ${new Date().toISOString()}`,
  ``
];

for (const [section, cmds] of Object.entries(commands)) {
  lines.push(`## ${section}`);
  lines.push('');
  for (const c of cmds) {
    lines.push('```bash');
    lines.push(c);
    lines.push('```');
    lines.push('');
  }
}

return [{
  json: {
    ok: true,
    domain,
    requestedSections,
    commands,
    markdown: lines.join('\n')
  }
}];
```

### `Is Valid Domain` (If node)

Condition:
- Value 1 expression: `{{$json.ok}}`
- Operation: `is true`

### `Success Response` (Respond to Webhook)

- Respond With: `JSON`
- Response Body Expression:

```javascript
={{$json}}
```

- Status Code: `200`

### `Error Response` (Respond to Webhook)

- Respond With: `JSON`
- Response Body Expression:

```javascript
={{$json}}
```

- Status Code: `400`

## 4) Connect Nodes

Create connections exactly:

1. `Manual Trigger` -> `Set Test Input`
2. `Set Test Input` -> `Normalize Input`
3. `Webhook Input` -> `Normalize Input`
4. `Normalize Input` -> `Command Templates`
5. `Command Templates` -> `Generate Commands`
6. `Generate Commands` -> `Is Valid Domain`
7. `Is Valid Domain` true -> `Success Response`
8. `Is Valid Domain` false -> `Error Response`

## 5) Test in Editor

1. Click `Execute workflow`.
2. Trigger from `Manual Trigger`.
3. Confirm output contains:
- `ok: true`
- `commands` object
- `markdown` with bash blocks

## 6) Test via Webhook

Example request:

```bash
curl -X POST 'https://YOUR_N8N_HOST/webhook/vulnscout/commands' \
  -H 'Content-Type: application/json' \
  -d '{"domain":"hackerone.com","requestedSections":["subdomain","urls","xss"]}'
```

## 7) Make It Production Ready (Still Free-Tier Friendly)

1. Add rate-limiting in reverse proxy (Nginx/Caddy) to protect webhook.
2. Add static auth header check in `Normalize Input`:
- Expect `x-api-key`.
- Reject if missing or invalid.
3. Store templates in a separate `Set` node or JSON file and version control it.
4. Add `Error Trigger` workflow for logging failures.

## 8) Optional Output Integrations (No Paid n8n Feature Needed)

You can branch after `Generate Commands` to:
1. `Discord` via `HTTP Request` webhook.
2. `Slack` via incoming webhook URL.
3. `Email` via SMTP node.
4. `Google Sheets` append rows for command history.

## 9) Troubleshooting

1. Webhook returns 404:
- Ensure workflow is `Active`.
- Use the production webhook URL, not test URL.

2. Invalid domain for valid target:
- Input must be bare domain like `example.com`.
- Strip protocol/path before sending.

3. Empty sections:
- Ensure `requestedSections` matches template keys exactly.

4. Commands not replacing domain:
- Confirm templates use exact `example.com` token.

## 10) Security and Legal Notes

1. Run commands only against assets you own or are authorized to test.
2. Keep logs for auditability in bug bounty work.
3. Do not automate destructive payload execution.

---

If you want, I can also generate an import-ready n8n workflow JSON file (`.json`) in this folder so you can import in one click.
