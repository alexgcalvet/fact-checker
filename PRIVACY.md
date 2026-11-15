# Privacy

fact-checker runs on your machine. Your flag files, marks, settings and keys stay in `~/.fact-checker/`. Something leaves your machine only for the author's collector, and only after you answer **Sí, compartir** (**Yes, share**) to the question that the player asks once.

## What the collector keeps

The collector is a Cloudflare Worker with a D1 database, run by the author.

| When | It keeps |
|---|---|
| You mark a card | The video id, the flag id, its second, type and label, the quote, the confidence, your verdict (correct or unfair) and your reason, the provider and model that made the flag, the helper version, a random install id and the time it arrived |
| You finish a whole analysis | The flags with their sources and the judge's verdicts, the video id, title, channel, date and length, the speaker names, the languages, the provider and model of each step, the cost, the helper version, a random install id and the time it arrived |
| Each day you send | A count of your requests per install id, for the daily limit |

The install id is a random number made once on your machine (`~/.fact-checker/install-id`). It groups the marks of one tester; it does not say who you are.

An analysis you upload waits for the author's review. Once approved, anyone who opens that video gets its flags, without your install id.

## What it never keeps

- Your name, email, account or IP address.
- The transcript or the audio of a video.
- Your file paths, settings or keys.

Cloudflare sees your IP address when a request arrives, as any web server does. The collector's code does not read it or keep it.

## Turn sharing off

- Answer **No** to the question, or untick **Compartir mis marcas y análisis** (**Share my marks and analyses**) in ⚙ of the side panel.
- This writes `share_marks = false` in `~/.fact-checker/config.toml`. A mark or analysis made while sharing is off is never sent.
- Shared analyses of other people still reach you with sharing off. That download sends no install id.

## Ask for deletion

Send an email to `<owner email>` with your install id (the content of `~/.fact-checker/install-id`). The author deletes every mark and analysis with that id.
