<div align="center">

<img src="src/extension/icons/icon128.png" width="96" alt="fact-checker">

# fact-checker

**A second, critical ear for YouTube.**<br>
Fallacies, false figures, contradictions and dodged questions, flagged at the second they are said.

[Install in one sentence](INSTALL-AGENT.md) · [How it works](#-how-it-works) · [Privacy](PRIVACY.md) · [Contributing](CONTRIBUTING.md)

![status](https://img.shields.io/badge/status-beta-E6DCC4)
![languages](https://img.shields.io/badge/videos-espa%C3%B1ol%20%7C%20English-9DB2D6)
![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-C4B5E8)
![browser](https://img.shields.io/badge/browser-Chrome-A8EBE6)
[![license](https://img.shields.io/badge/license-MIT-E6DCC4)](LICENSE)

</div>

---

> ⚠️ **Automatic signals, not verdicts.** Every flag quotes the exact words, gives a short reason and a confidence, and names its sources. It never calls anyone a liar. It can be wrong: tell it with **✗ Disagree**.

## ✨ What it flags

| | Flag | What triggers it |
|---|---|---|
| 🔴 | **False or misleading figure** | a number that official statistics contradict, or a true number used to suggest something it does not show |
| 🟣 | **Fallacy** | an attack on the person, a straw man, "and you more" (tu quoque), cherry-picked data, an appeal to fear |
| 🟣 | **Contradiction** | the speaker says the opposite of what they said earlier in the same video |
| 🟣 | **Dodged question** | an answer that does not answer what the host asked |
| ⚪ | **Nitpick** | a small slip that does not change the argument, such as a figure off by a few percent |
| 🔵 | **Context** | background that helps to follow a reference, without judging it |

## 🧭 How it works

**▶️ YouTube video** → **💻 helper on your machine** → **🤖 your Claude or ChatGPT** → **🏷️ flags on the player**

1. You click **Analyze this video** on the player.
2. A small helper on your machine reads the captions, or transcribes the audio, and sends each two-minute part to your own AI subscription, a little ahead of where you are watching.
3. Figures are checked on the web against official sources. A final pass rereads the whole video and drops flags that do not hold.
4. Flags appear on the player at their second, and in a side panel with every flag of the video.

Your conversations and keys stay on your machine. Nothing is shared unless you say yes.

## 🚀 Install

Paste one sentence into **Claude** (Claude Code or the Claude desktop app) or **ChatGPT** (Codex). The assistant installs everything.

### 🇪🇸 Español

```
Instala fact-checker siguiendo https://github.com/alexgcalvet/fact-checker/blob/main/INSTALL-AGENT.md
```

Tu asistente lo instala todo. Tú solo inicias sesión en el navegador cuando te lo pida y haces tres clics en Chrome para cargar la extensión. Nunca pegues una clave en el chat.

### 🇬🇧 English

```
Install fact-checker by following https://github.com/alexgcalvet/fact-checker/blob/main/INSTALL-AGENT.md
```

Your assistant installs everything. You only log in in the browser when it asks, and click three times in Chrome to load the extension. Never paste a key in the chat.

You need a Claude or ChatGPT subscription with Claude Code or Codex.

<details>
<summary>Install by hand, use an API key or another model</summary>

See [docs/configuration.md](docs/configuration.md): manual install, the settings file, providers (Claude, Codex, Anthropic API, OpenAI or Grok, any chat API such as Hugging Face or a local Ollama), optional keys and the feedback options.

</details>

## 🎬 Use

1. Open a Spanish or English video on YouTube.
2. Click **Analyze this video** (**Analizar este vídeo**) on the player and keep watching. Flags appear as the video plays.
3. On each card, answer **Is this flag fair?** with **✓ Agree** or **✗ Disagree**.
4. Open **Flags** at the side of the player to see every flag, jump to its second, or export a summary image to share.
5. If the player says that the helper does not answer, ask your assistant to run `fact-checker doctor`.

The interface follows your browser's language. Change it in ⚙ in the side panel.

> 💳 **What an analysis spends.** It uses your Claude or ChatGPT subscription: a one-hour video spends a notable share of your usage limit. The line under **Analyze this video** says which subscription or account pays. If someone already analysed the video and the author approved it, you get that **shared analysis** at once, for free.

## 🔒 Privacy

- Everything stays in `~/.fact-checker/` on your machine: transcripts, flags, your marks.
- The first time you mark a card or analyse a video, the player asks once whether to share your marks and analyses with the author to improve the detector. Nothing leaves your machine before you say yes, and you can change it any time in ⚙.
- Transcripts, names, emails, IP addresses and keys are never sent. The full list is in [PRIVACY.md](PRIVACY.md).

## 🚧 Limits

- **Beta.** Precision is measured on a small set of marked interviews, and it improves with your marks.
- It knows what was said in the video and what it finds on the web at that moment. It does not yet know a speaker's long-term record.
- Videos without captions are transcribed on your machine, which takes time: about 35 minutes for a one-hour video on a laptop CPU.
- Spanish and English only. Windows is not supported yet.

## 🤝 Contributing

Help is welcome, most of all to **review flags**, build **test dialogues**, add **official data sources** per country, analyse a speaker's **track record** and **calibrate** the detector from feedback. Start with [CONTRIBUTING.md](CONTRIBUTING.md). To report a security problem, see [SECURITY.md](SECURITY.md).

---

## Third-party software

The setup downloads these tools onto your machine. They are not part of this repo and keep their own licences.

| Tool | Used for | Licence |
|---|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | captions and audio of a video | Unlicense |
| [FFmpeg](https://ffmpeg.org/legal.html), a static build | audio for speech to text | LGPL or GPL, depending on the build |
| mlx-whisper or faster-whisper, and their speech model | speech to text on your machine | MIT |
| pyannote (only with `HF_TOKEN`) | speaker separation | MIT; the model has its own terms on Hugging Face |

## Licence

[MIT](LICENSE) © 2026 Alex G. Calvet. Free to use, change and share, keeping the copyright notice.
