# Security

## Report a problem

Do not open a public issue for a security problem. Use GitHub's private vulnerability reporting on this repository (Security → Report a vulnerability). Say what you found, how to reproduce it and what it affects.

You get an answer within 7 days. A fix and a public note follow once users are safe.

## What is in scope

| Part | Examples |
|---|---|
| Feedback collector (`src/collector/`) | reading other people's marks without the admin token, storing or serving a shared analysis without approval, bypassing the size or rate limits |
| Local helper (`src/helper/`) | a web page or video that makes the helper run a command, read a file or send data elsewhere; a key printed or logged |
| Extension (`src/extension/`) | script injection through a flag, a quote, a reason or a source link |

Out of scope: the security of YouTube, Claude Code, Codex, the model APIs and Cloudflare themselves.
