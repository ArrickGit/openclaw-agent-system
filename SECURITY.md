# Security and Privacy

This repository is a **sanitized public showcase** of a personal AI agent system. It was written
from scratch for publication. It is not an export of the private system.

## What is intentionally excluded

- API keys, tokens, passwords, cookies, session data, and environment variables
- Messaging-platform user IDs, server or channel names, usernames, and private messages
- Email addresses and personal account details
- Absolute local file paths and machine-specific configuration
- Raw logs, screenshots, raw browser text, and private conversations
- Agent system prompts, private configuration, internal tool schemas, scheduler identifiers,
  and infrastructure details
- Real market prices or listings collected by the private monitors

## What is included

- Architecture descriptions written at a level safe to publish
- A small, standard-library-only demo that makes **no network calls**, uses **no credentials**,
  and sends **no messages**
- Example reports and an incident write-up that use **fictional, clearly labeled simulated data**

## Safety properties of the real workflows (described, not shipped)

- **Read-only collection**: the game-market monitor reads pages. It does not post, reply,
  message anyone, or buy anything.
- **No trading**: the stock observer produces research notes. It has no brokerage access and
  does not place orders.
- **Validation before external action**: delivery runs only after validation passes.
- **Least privilege for the debugging agent**: Hermes reviews evidence and proposes repairs.
  It does not expose credentials and does not change systems without explicit authorization.

## If you fork this

- Keep secrets in environment variables or a secret manager, never in the repository.
  `.gitignore` already excludes common secret and local-state files.
- Respect the terms of service of any site you automate. Keep automation read-only unless you
  have permission to do more.

## Reporting

If you find anything here that looks like a real credential or private identifier, please open
an issue on this repository without quoting the value, and it will be removed.
