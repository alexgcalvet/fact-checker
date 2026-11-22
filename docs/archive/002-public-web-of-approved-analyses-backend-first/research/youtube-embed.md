# YouTube embed: part 1, the IFrame Player API (2026-11-20)

Sources: [IFrame Player API reference](https://developers.google.com/youtube/iframe_api_reference), [Player parameters](https://developers.google.com/youtube/player_parameters), read 2026-11-20. Facts marked *(summary)* come from the part of the reference that was read as a summary, not word by word; the S3 contract test checks them against a real embed.

Part 2, the policy on elements over an embed (overlay, cinema mode), belongs to the frontend RFC in the brand repo.

## Conclusion

The test page (S3) can drive the extension panel from an embed: it reads the time with `getCurrentTime()`, polls it (the API has no time event), and seeks with `seekTo()`. A video whose owner blocks embedding fails with error 101 or 150; the page then links to YouTube.

## Load and create

| Item | Contract |
|---|---|
| Script | `<script src="https://www.youtube.com/iframe_api">` |
| Ready callback | the API calls the global `onYouTubeIframeAPIReady()` once the script loads |
| Player | `new YT.Player(elementOrId, {videoId, width, height, playerVars, events})`; defaults 640 × 390 |
| `playerVars` | `playsinline: 1` (inline on iOS; the default `0` opens fullscreen), `enablejsapi: 1` (API control), `origin: <page origin>` (security, set it when the API is used), `start: <s>` (seeks to the nearest keyframe, up to about 2 s early), `fs: 0` hides the fullscreen button, `rel: 0` limits related videos to the same channel |
| Size | viewport at least 200 × 200 px; 16:9 players at least 480 × 270 recommended |
| Browser | needs `postMessage` |

## Read and move the time

| Need | Call | Returns or does |
|---|---|---|
| Current time | `getCurrentTime()` | seconds, Number *(summary)* |
| Duration | `getDuration()` | seconds, Number; 0 until the metadata loads; on a live stream, the time the stream has run, often longer than the event *(summary)* |
| Seek | `seekTo(seconds, allowSeekAhead)` | a paused player stays paused, otherwise it plays; `allowSeekAhead = true` fetches outside the buffer (use `false` while dragging, `true` on release) |
| Play, pause | `playVideo()`, `pauseVideo()` | end in state 1 and 2 |
| State | `getPlayerState()` | a state number *(summary)* |

## Events

| Event | Data |
|---|---|
| `onReady` | the player accepts API calls; no data *(summary)* |
| `onStateChange` | `-1` unstarted, `0` ended, `1` playing, `2` paused, `3` buffering, `5` cued; constants `YT.PlayerState.ENDED`, `PLAYING`, `PAUSED`, `BUFFERING`, `CUED` *(summary)* |
| `onError` | `2` invalid parameter, `5` not playable in HTML5, `100` not found, private or removed, **`101` and `150` the owner does not allow embedding**, `153` missing Referer or client identification *(summary)* |
| Time update | none found; poll `getCurrentTime()` |

## Fit with the extension panel

- The panel reads `currentTime`, `duration` and the events `timeupdate` and `durationchange` of an `HTMLVideoElement`. An adapter over the player gives the same: a timer of about 250 ms polls `getCurrentTime()` and emits `timeupdate`; `onStateChange` to playing emits `durationchange` once `getDuration()` is above 0.
- A click on a flag calls `seekTo(second, true)`.
- Error 153 means the page sends no Referer: serve the test page with a referrer policy that keeps the origin.

## Open for S3

- Check the *(summary)* facts in the S3 contract test with one real public video.
- Fullscreen of the iframe hides the panel; the RFC handles it with cinema mode and the overlay (frontend RFC).
