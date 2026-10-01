# Long Division Lab

A browser game that walks Grade 6 students through long division one step at a time
(divide → multiply → subtract → bring down), with a scribble layer for drawing on the
"paper", points, streaks, badges, confetti, and optional AI hints.

## Run

```bash
cd ~/code/longdivision
cp .env.example .env      # add ANTHROPIC_API_KEY or OPENAI_API_KEY (optional)
python3 server.py         # http://localhost:8765
```

No dependencies beyond Python 3. Without a key, hints fall back to built-in ones.

## Play

- Pick a level, A to F (1-digit divisors up to a 5-digit ÷ 2-digit boss level) or type your own problem.
- Type the digit(s) for the highlighted boxes, press Enter. ↓ or Space brings the next digit down.
- **Scribble** (or `S`) turns on drawing so students can circle numbers, write times tables, etc.
- `H` asks Professor Hoot for a hint (costs 3 points). `N` = new problem.

Scoring: 10 pts per quotient digit, 5 per multiply/subtract, streak ×2 after 5 in a row,
+25 for a flawless problem, +10 for no hints.

## Deployment (division.dyob.ca)

- Runs in **LXC 211 "division" on pve9** (Debian 13, 1 core / 512 MB, DHCP, currently 192.168.180.182).
  App at `/opt/longdivision`, systemd unit `longdivision.service`, listens on port 8765 as `www-data`.
- Update: `tar -czf /tmp/ld.tgz public server.py README.md .env.example`, scp to pve9, `pct push 211 …`,
  extract into `/opt/longdivision`, then `systemctl restart longdivision`.
- API key: put `ANTHROPIC_API_KEY=…` in `/opt/longdivision/.env` (chmod 600, owner www-data) and restart.
- DNS: proxied A record `division.dyob.ca` → studio IP, same as www.dyob.ca. Public traffic reaches the
  studio Nginx Proxy Manager (192.168.180.111), which needs a proxy host
  `division.dyob.ca → http://192.168.180.182:8765` with SSL.
