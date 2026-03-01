# Multi-site routing (many Pis, many screens)

This explains how commands are routed to the correct Raspberry Pi when you have multiple sites.

## Core rule

Each screen must have an `agentId` saved in the app.

- Each Pi runs `option_b_agent.py` with one unique `AGENT_ID`.
- The frontend sends remote jobs with `agent_id` = that screen `agentId`.
- Cloud backend queues by `agent_id`.
- Only the Pi with matching `AGENT_ID` polls and executes that job locally.

## Recommended naming scheme

Use stable IDs per site:

- `site-bucharest`
- `site-london`
- `site-berlin`

Avoid spaces and special characters.

## Example with 3 sites x 10 screens

- Pi at Bucharest hostname: `site-bucharest` (leave `AGENT_ID` empty or set `AGENT_ID=$(hostname)`)
- Pi at London hostname: `site-london` (leave `AGENT_ID` empty or set `AGENT_ID=$(hostname)`)
- Pi at Berlin hostname: `site-berlin` (leave `AGENT_ID` empty or set `AGENT_ID=$(hostname)`)

For every Bucharest screen, set `agentId=site-bucharest` in the dashboard.
For every London screen, set `agentId=site-london`.
For every Berlin screen, set `agentId=site-berlin`.

Then routing is automatic.

## Required CSV headers for import

Use these exact headers (case-insensitive):

`name,ip,port,displayId,protocol,agentId,site,city,zone,area,description`

Notes:

- `ip` is required.
- `displayId` defaults to `0` if empty.
- `port` defaults to `1515` if empty.
- `protocol` defaults to `AUTO` if empty.

## Quick verification checklist

1. On each Pi, confirm unique `AGENT_ID`.
2. In dashboard, confirm each screen has the correct `agentId`.
3. In cloud backend, verify heartbeat shows all agents: `GET /api/remote/agents`.
4. Test one screen per site.
5. Run "Refresh all".

## Common mistakes

- Same `AGENT_ID` used on 2 different Pis.
- Wrong `agentId` assigned to screens in CSV.
- Empty `agentId` for remote-only sites.
- Using local screen IPs from the wrong LAN/site.
