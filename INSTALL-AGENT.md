# Install fact-checker: guide for an AI agent

You are an AI agent, such as Claude Code, the Claude desktop app or Codex. You run on the person's macOS or Linux machine. The person asked you to install fact-checker, or to repair it. Follow the steps in order.

fact-checker is a Chrome extension and a small helper program. The helper reads YouTube videos with the person's own Claude or ChatGPT subscription.

## Rules

- Speak to the person in their language. Use the **ES** text for Spanish and the **EN** text for English.
- Do every step yourself. Run every command yourself. Ask the person only when a step shows a message for the person.
- If a command fails with "Operation not permitted", your sandbox blocked it. Ask the person to approve the command. Then run the same command again outside your sandbox.
- Never run `fact-checker serve`. `fact-checker setup` starts the helper at every login.
- Never ask the person to paste a key, a token or a password into the chat.
- A key goes in only through the helper's key page: on YouTube, ⚙ → Claves (Keys). If the person prefers a terminal, `fact-checker key set <NAME>` also works.
- Never read, print or edit `~/.fact-checker/.env`.
- Never run `sudo`.
- If a command fails, read its output. Then run `fact-checker doctor --json` and follow step 4.

## 1. Check the system

```sh
uname -s
```

- If the output is `Darwin` or `Linux`, go to step 2.
- If not, stop. Tell the person this message.

> **ES:** fact-checker funciona por ahora solo en macOS y Linux. Todavía no funciona en Windows.\
> **EN:** fact-checker works only on macOS and Linux for now. It does not work on Windows yet.

## 2. Find the logged-in subscription

The helper needs Claude Code (`claude`) or Codex (`codex`), logged in to the person's subscription.

```sh
claude auth status --json
codex login status
```

- If `claude` prints `"loggedIn": true`, go to step 3.
- If `codex login status` exits with 0, go to step 3.
- If you are Claude, use Claude. If you are Codex or ChatGPT, use Codex.
- If you do not know the subscription of the person, ask with this message.

> **ES:** ¿Qué suscripción pagas: Claude o ChatGPT? fact-checker la usa para analizar los vídeos.\
> **EN:** Which subscription do you pay for: Claude or ChatGPT? fact-checker uses it to analyse the videos.

For Claude: if `claude` is missing, install it. Then log in.

```sh
curl -fsSL https://claude.ai/install.sh | bash
claude auth login
```

For ChatGPT: if `codex` is missing, install it. Then log in.

```sh
curl -fsSL https://chatgpt.com/codex/install.sh | sh
codex login
```

Before you run `claude auth login` or `codex login`, tell the person this message.

> **ES:** Se abrirá una ventana del navegador. Inicia sesión con tu cuenta de Claude o ChatGPT y vuelve aquí.\
> **EN:** A browser window will open. Log in with your Claude or ChatGPT account, then come back here.

## 3. Run the installer

The installer installs uv, yt-dlp, ffmpeg and the helper. Then it starts the helper at every login. It is safe to run again.

Name yourself with `--provider`: the helper reads with the subscription of the agent that installs it.

- If you are Codex, use `--provider codex`.
- If you are Claude Code or the Claude app, use `--provider claude`.

The commands below show Codex. Change the last word if you are Claude.

- If you are in a folder of the fact-checker repository, run the installer from there.

```sh
./install.sh --provider codex
```

- If not, download and run it.

```sh
curl -fsSL https://raw.githubusercontent.com/alexgcalvet/fact-checker/main/install.sh | sh -s -- --provider codex
```

The last line of the output names the extension folder, such as `/Users/ana/.fact-checker/extension`. Keep this path for step 5.

## 4. Check the install

```sh
fact-checker doctor --json
```

The output is one JSON object. `"ok"` is `true` when everything works. Each item of `"checks"` has a `name`, a `state`, a `fix` and `ok`.

- If `"ok"` is `true`, go to step 5.
- If not, fix each check with `"ok": false`, then run `fact-checker doctor --json` again.

| Check with `"ok": false` | What you do |
|---|---|
| `claude` or `codex` | Go to step 2 |
| `chrome` | Tell the person the Chrome message below. Then run `fact-checker setup` |
| `helper`, with the state `blocked by the agent's sandbox` | Ask the person to approve. Then run `fact-checker setup` and `fact-checker doctor --json` outside your sandbox |
| `helper`, with any other state | Run `fact-checker setup` |
| A variable name, such as `ANTHROPIC_API_KEY` | Do step 5 first if the extension is not loaded. Then tell the person the key message below, with that name |
| Any other check | Run the command in its `fix` |

> **ES:** Falta Google Chrome. Descárgalo de https://www.google.com/chrome/ e instálalo. Avísame cuando esté.\
> **EN:** Google Chrome is missing. Download it from https://www.google.com/chrome/ and install it. Tell me when it is done.

> **ES:** Hace falta una clave. Abre un vídeo de YouTube, abre el panel de avisos y pulsa ⚙ → Claves. Pega tu clave en el campo de `ANTHROPIC_API_KEY` y pulsa Guardar: no se verá. Nunca la pegues en este chat.\
> **EN:** A key is needed. Open a YouTube video, open the flags panel and click ⚙ → Keys. Paste your key in the `ANTHROPIC_API_KEY` field and click Save: it stays hidden. Never paste it in this chat.

The helper uses a key from the key page at once. Run `fact-checker doctor --json` again. If the person used `fact-checker key set`, run `fact-checker setup` first to restart the helper.

## 5. Load the extension in Chrome

Chrome does not let you do this step. Tell the person this message, with the folder path of step 3.

> **ES:** Último paso, en Chrome: 1) Escribe chrome://extensions en la barra de direcciones y pulsa Intro. 2) Activa «Modo de desarrollador», arriba a la derecha. 3) Pulsa «Cargar descomprimida» y elige la carpeta <ruta>. La carpeta está oculta: en Mac pulsa Cmd+Mayús+G y pega la ruta; en Linux pulsa Ctrl+L.\
> **EN:** Last step, in Chrome: 1) Type chrome://extensions in the address bar and press Enter. 2) Turn on "Developer mode", top right. 3) Click "Load unpacked" and choose the folder <path>. The folder is hidden: on a Mac press Cmd+Shift+G and paste the path; on Linux press Ctrl+L.

## 6. Finish

Tell the person this message.

> **ES:** Listo. Abre un vídeo de YouTube en español o en inglés y pulsa «Analizar este vídeo» en el reproductor.\
> **EN:** Done. Open a YouTube video in English or Spanish and click "Analyze this video" on the player.

## Repair and update

- If the player says that the helper does not answer, run `fact-checker doctor --json`. Then follow step 4.
- If the person asks to read with the other subscription, run `fact-checker provider codex` or `fact-checker provider claude`. It restarts the helper.
- To update from a clone, run these commands in the repository folder.

```sh
git pull
uv tool install --reinstall ./src/helper
fact-checker setup
```

- Without a clone, run the second command with the archive address, then `fact-checker setup`.

```sh
uv tool install --reinstall "fact-checker @ https://github.com/alexgcalvet/fact-checker/archive/refs/heads/main.tar.gz#subdirectory=src/helper"
fact-checker setup
```

- After an update, tell the person this message.

> **ES:** He actualizado fact-checker. En chrome://extensions, pulsa el icono de recargar de fact-checker.\
> **EN:** I updated fact-checker. In chrome://extensions, click the reload icon of fact-checker.
