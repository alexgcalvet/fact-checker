// A fake YT.Player of the YouTube IFrame Player API (docs/archive/002-public-web-of-approved-analyses-backend-first/research/youtube-embed.md): the calls the web viewer makes,
// and controls for the test to fire the player's events. Like the real one, it puts an iframe in place of its element.
export class FakePlayer {
  static last: FakePlayer | undefined;
  time = 0;
  duration = 0;
  state = -1;
  seeks: [number, boolean][] = [];
  pauses = 0;
  volume = 100;
  muted = false;
  destroyed = false;
  iframe = document.createElement("iframe");

  constructor(element: HTMLElement, public options: any) {
    FakePlayer.last = this;
    element.replaceWith(this.iframe);
  }

  getCurrentTime() { return this.time; }
  getDuration() { return this.duration; }
  getPlayerState() { return this.state; }
  getIframe() { return this.iframe; }
  seekTo(seconds: number, allowSeekAhead: boolean) {
    this.seeks.push([seconds, allowSeekAhead]);
    this.time = seconds;
  }
  playVideo() { this.state = 1; }
  pauseVideo() {
    this.pauses++;
    this.state = 2;
  }
  getVolume() { return this.volume; }
  setVolume(volume: number) { this.volume = volume; }
  mute() { this.muted = true; }
  unMute() { this.muted = false; }
  /** Removes the player's iframe, as the real one does. */
  destroy() {
    this.destroyed = true;
    this.iframe.remove();
  }

  /** The API accepts calls: `onReady`. */
  ready() { this.options.events?.onReady?.({ target: this }); }
  /** The video plays at `at` seconds, with its metadata loaded. */
  play(at: number, duration = 3600) {
    this.duration = duration;
    this.time = at;
    this.state = 1;
    this.options.events?.onStateChange?.({ target: this, data: 1 });
  }
  /** The video moves on to `at` seconds while it plays. */
  reach(at: number) { this.time = at; }
  /** The player fails with an error code: `onError`. */
  fail(code: number) { this.options.events?.onError?.({ target: this, data: code }); }
}
