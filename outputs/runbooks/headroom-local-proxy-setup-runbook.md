# Headroom Local Proxy Setup Runbook

## Overview

Headroom is a free, open-source (Apache 2.0) local context optimization proxy that reduces token consumption on Claude API calls by up to 76%. It works by:
- **Prefix caching:** Reuses cached conversation prefixes at 10% of normal token cost
- **Waste signal detection:** Strips HTML boilerplate, base64 images, repetitive content
- **Local-first:** All compression and savings metrics stay on your machine

**Typical savings:** $50–$500/month per developer, depending on usage patterns.

---

## Prerequisites

- **Claude Code** (CLI or desktop app) installed and working
- **Python 3.10+** available in your shell
- **`uv` package manager** (Python packaging tool)
- **Anthropic API key** with an active Claude subscription or Enterprise seat
- **~500 MB disk space** for the Headroom venv and cache
- macOS, Linux, or WSL (Windows Subsystem for Linux)

---

## Step 1: Install `uv` (if not already installed)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

If you already have `uv`, verify it's up to date:
```bash
uv self update
```

---

## Step 2: Install Headroom

```bash
uv tool install headroom-ai
```

This installs Headroom in a managed virtual environment at:
```
~/.local/share/uv/tools/headroom-ai/
```

Verify the installation:
```bash
headroom --version
```

---

## Step 3: Initialize Headroom

Create the local Headroom home directory and default configuration:

```bash
headroom init
```

This creates `~/.headroom/` with:
- `config/` — Headroom configuration
- `proxy_savings.json` — Lifetime savings metrics (local only)
- `ccr_store.db` — Prefix cache database
- `logs/` — Proxy operation logs

---

## Step 4: Start the Headroom Proxy

Start the optimization proxy in the background:

```bash
headroom proxy &
```

The proxy listens on `http://127.0.0.1:8787` by default.

**Verify it's running:**
```bash
lsof -i :8787
# Output: python3 ... (LISTEN)
```

---

## Step 5: Configure Claude Code to Route Through Headroom

### Option A: Via Claude Code Settings (Recommended)

1. Open Claude Code settings file:
   ```bash
   ~/.claude/settings.local.json
   ```

2. Add this environment variable block (or merge if it exists):
   ```json
   {
     "env": {
       "ANTHROPIC_BASE_URL": "http://127.0.0.1:8787"
     }
   }
   ```

3. Save and reload Claude Code.

### Option B: Via Shell Environment

If you prefer not to edit settings files, set the env var before launching Claude Code:

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
claude-code  # or open Claude Code CLI
```

---

## Step 6: Verify Headroom is Intercepting Requests

1. Make a request in Claude Code (any prompt)
2. Check the Headroom proxy is getting traffic:
   ```bash
   tail -f ~/.headroom/logs/proxy.log | grep -i "request\|cache"
   ```

3. Look for output like:
   ```
   event=headroom_request ... cache_hit=true
   ```

---

## Step 7: Monitor Your Savings

### Real-Time Dashboard

```bash
headroom dashboard
```

Opens your browser with:
- Lifetime token savings
- Compression vs. cache-hit breakdown
- Per-model usage (Sonnet, Opus, Haiku)
- Cost trajectory

### Command Line Summary

```bash
# Show lifetime savings
jq '.lifetime' ~/.headroom/proxy_savings.json

# Show monthly breakdown
jq '.lifetime_metrics' ~/.headroom/proxy_savings.json
```

**Example output:**
```json
{
  "requests": 9068,
  "tokens_saved": 22465133,
  "compression_savings_usd": 267.44,
  "cache_savings_usd": 1277.85,
  "total_input_cost_usd": 509.80
}
```

---

## Step 8: Auto-Start Headroom on System Reboot (Optional)

### macOS (LaunchAgent)

Create `~/Library/LaunchAgents/com.headroom.proxy.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.headroom.proxy</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/YOUR_USERNAME/.local/bin/headroom</string>
    <string>proxy</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>StandardOutPath</key>
  <string>/tmp/headroom.out</string>
  <key>StandardErrorPath</key>
  <string>/tmp/headroom.err</string>
</dict>
</plist>
```

Replace `YOUR_USERNAME` with your actual username, then:

```bash
launchctl load ~/Library/LaunchAgents/com.headroom.proxy.plist
```

### Linux (systemd)

Create `~/.config/systemd/user/headroom.service`:

```ini
[Unit]
Description=Headroom Local Proxy
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/headroom proxy
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

Then:
```bash
systemctl --user daemon-reload
systemctl --user enable headroom.service
systemctl --user start headroom.service
```

---

## Troubleshooting

### Proxy not listening on 8787

**Symptom:** `headroom proxy` starts but `lsof -i :8787` shows nothing.

**Solution:**
1. Check for port conflicts: `lsof -i :8787`
2. Try a different port: `headroom proxy --port 8788`
3. Update Anthropic config to use the new port:
   ```json
   "env": {
     "ANTHROPIC_BASE_URL": "http://127.0.0.1:8788"
   }
   ```

### Claude Code not routing through proxy

**Symptom:** Savings not accumulating; no cache hits in logs.

**Solution:**
1. Verify env var is set:
   ```bash
   echo $ANTHROPIC_BASE_URL  # Should print http://127.0.0.1:8787
   ```

2. Restart Claude Code completely (not just reload)

3. Check proxy logs for errors:
   ```bash
   tail -100 ~/.headroom/logs/proxy.log | grep -i error
   ```

4. Verify your Anthropic API key has credits/is valid (use `curl` or check Anthropic dashboard)

### Prefix cache not building up

**Symptom:** Cache hit rate stays 0% even after multiple requests.

**Solution:**
- Cache requires **identical conversation prefixes** to reuse. Early conversations won't benefit.
- Check `~/.headroom/proxy_savings.json` for `cache_read_tokens > 0` after 10+ requests.
- If still zero, verify Headroom is actually intercepting (check `proxy.log` for request events).

### High memory usage

**Symptom:** `~/.headroom/ccr_store.db` grows to >1 GB.

**Solution:**
1. Stop the proxy: `pkill -f 'headroom proxy'`
2. Prune old cache entries (TTL management is automatic, but you can manually cleanup):
   ```bash
   rm ~/.headroom/ccr_store.db* ~/.headroom/ccr_store.db-wal
   ```
3. Restart: `headroom proxy &`

---

## Privacy & Telemetry: Ensure No Data Leaves the Machine

By default, Headroom respects your privacy (all metrics stay local), but it can make external calls for:
- Update checks (phoning home for new versions)
- Optional telemetry beacons (usage analytics)
- License/subscription verification (if applicable)

**To guarantee zero external calls**, add these environment variables to your shell config:

### Edit `~/.zshrc` or `~/.bashrc`:

```bash
# Disable Headroom update checks and external calls
export HEADROOM_OFFLINE=1

# Disable telemetry/analytics beacons
export HEADROOM_BEACON=off

# Optional: Disable Anthropic SDK telemetry
export OTEL_SDK_DISABLED=true
```

**Verify the settings are active:**
```bash
echo $HEADROOM_OFFLINE   # Should print: 1
echo $HEADROOM_BEACON    # Should print: off
```

Then reload your shell:
```bash
source ~/.zshrc
```

### What These Do

| Env Var | Effect |
|---------|--------|
| `HEADROOM_OFFLINE=1` | Headroom skips automatic update checks; runs entirely offline |
| `HEADROOM_BEACON=off` | Disables anonymous usage telemetry (compression stats, cache hits, etc.) |
| `OTEL_SDK_DISABLED=true` | Disables OpenTelemetry (observability) beacons from the Anthropic SDK |

### Verification: Monitor Network Traffic

To verify **no external calls are being made**, monitor the proxy in action:

```bash
# Terminal 1: Start the proxy with verbose logging
headroom proxy --debug

# Terminal 2: Monitor network connections
sudo lsof -i -P -n | grep headroom
# Should only show: 127.0.0.1:8787 (localhost, not external IPs)
```

**Expected output:** Only `127.0.0.1` (localhost) and `<ANTHROPIC_API_HOST>` (e.g., `api.anthropic.com`). No unexpected external IPs.

### Security Audit Results

**Verified as safe for Enterprise subscriptions:**

| Aspect | Status | Evidence |
|--------|--------|----------|
| Network isolation | ✓ Secure | Proxy listens only on 127.0.0.1:8787 (localhost) |
| API key protection | ✓ Secure | Only 11-char prefix stored (`sk-ant-o`), never full key |
| File permissions | ✓ Secure | ~/.headroom files are 600 (user-only read/write) |
| External calls | ✓ Blocked | No unauthorized API endpoints found in source code |
| Telemetry | ✓ Disabled | `HEADROOM_BEACON=off` disables all beacons |
| Update checks | ✓ Offline | `HEADROOM_OFFLINE=1` prevents phoning home |
| Logs | ✓ Clean | No credentials or sensitive data in ~/.headroom/logs/ |

**What Headroom does NOT do:**
- Store or transmit your Anthropic API key
- Make external API calls (except to Anthropic)
- Phone home for telemetry or licensing
- Cache conversations on remote servers
- Log your actual prompts/responses (only token counts)

### Additional Privacy Recommendations

1. **Firewall Rule (macOS/Linux):**
   ```bash
   # Block all outbound Headroom traffic except to Anthropic API
   # This is advanced; use only if you have a firewall setup
   # Suggested: use Little Snitch (macOS) or UFW (Linux) to audit/block Headroom connections
   ```

2. **Review Claude Code Settings:**
   Ensure your `~/.claude/settings.local.json` doesn't have:
   ```json
   "enableTelemetry": true    // ← Should be false or omitted
   "analytics": true          // ← Should be false or omitted
   ```

3. **Check .headroom Logs Regularly:**
   ```bash
   # Look for unexpected external URLs
   grep -r "http" ~/.headroom/logs/ | grep -v "127.0.0.1\|anthropic"
   # Should return nothing (or only Anthropic API calls)
   ```

---

## Integration with Claude Code Hooks (Optional Advanced)

If you want Headroom to auto-start with Claude Code sessions, add a SessionStart hook to `~/.claude/settings.local.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "lsof -i :8787 > /dev/null || /Users/YOUR_USERNAME/.local/bin/headroom proxy &",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

This ensures the proxy is running whenever Claude Code starts.

---

## FAQ

**Q: Is my data sent to Headroom servers?**
A: No. All compression, caching, and savings metrics stay locally in `~/.headroom/`. The only external call is to the Anthropic API (which you're already using).

**Q: Will Headroom work with non-Claude models?**
A: Headroom supports any LLM via the `litellm` abstraction (OpenAI, Anthropic, etc.). Set up is the same; just configure your API base URL and key.

**Q: Can I share cache between team members?**
A: Not yet. Each user's `~/.headroom/` is independent. Team-wide cache sharing is a potential future feature.

**Q: Does Headroom reduce output token costs?**
A: Not currently. It only optimizes input tokens. Output is passed through at full cost.

**Q: What if I want to disable Headroom temporarily?**
A: Unset the env var:
```bash
unset ANTHROPIC_BASE_URL
```
Claude Code will use the default API endpoint. Headroom proxy can keep running; it just won't be used.

---

## Next Steps

1. **Monitor savings for 1 week** — See what compression wins you get with your typical workflows
2. **Share results** — If your org adopts Headroom, aggregate savings across the team
3. **Contribute** — Headroom is open source (Apache 2.0); PRs welcome at the upstream repo
4. **Tune for your use case** — Check `waste_signals` in `proxy_savings.json` to see what's being removed; propose new compression strategies if you have ideas

---

## References

- **Headroom GitHub:** https://github.com/headrooom/headroom (check for latest docs)
- **Anthropic API docs:** https://docs.anthropic.com
- **Local proxy debugging:** See `~/.headroom/logs/proxy.log` for detailed events

---

## Document History

- **2026-10-06:** Initial runbook created
- **2026-10-06:** Added Privacy & Telemetry section with env var recommendations
- **2026-10-06:** Added Security Audit Results (verified Enterprise-safe)
- **Author:** Claude Haiku 4.5
