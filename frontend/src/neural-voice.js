// Server-side TTS. Only the current persisted assistant reply can be synthesized.
export default class NeuralVoice {
  constructor({audio, getToken, onStatus = () => {}, onDone = () => {},
    fetcher = (...args) => fetch(...args), urls = URL,
    schedule = (fn, ms) => setTimeout(fn, ms), unschedule = id => clearTimeout(id)}) {
    // onDone hands the turn back to the caller; cancellation is an interruption, so it stays silent.
    Object.assign(this, {audio, getToken, onStatus, onDone, fetcher, urls, schedule, unschedule});
    this.generation = 0;
    this.controller = null;
    this.timer = null;
    this.url = null;
    this.key = null;
  }

  cancel() {
    this.generation++;
    this.controller?.abort();
    this.controller = null;
    if (this.timer !== null) this.unschedule(this.timer);
    this.timer = null;
    this.audio.onended = this.audio.onerror = null;
    this.audio.pause();
    this.audio.removeAttribute('src');
    this.audio.load();
    if (this.url) this.urls.revokeObjectURL(this.url);
    this.url = this.key = null;
    this.onStatus('');
  }

  async play(generation) {
    try {
      await this.audio.play();
      if (generation === this.generation) this.onStatus('Playing OpenAI neural voice');
    } catch (error) {
      if (generation !== this.generation) return;
      this.onStatus(error.name === 'NotAllowedError'
        ? 'Audio needs a click. Press Replay reply to listen.'
        : 'Audio playback failed. Try Replay reply or device voice.');
      this.onDone();
    }
  }

  async speak(session) {
    this.cancel();
    if (session.state === 'human') return;
    const generation = this.generation;
    const controller = new AbortController();
    this.controller = controller;
    this.key = `${session.id}:${session.revision}`;
    this.onStatus('Generating OpenAI neural voice…');
    this.timer = this.schedule(() => controller.abort(), 20000);
    try {
      const response = await this.fetcher('/api/speech', {
        method: 'POST', signal: controller.signal,
        headers: {'Content-Type': 'application/json', Authorization: `Bearer ${this.getToken()}`},
        body: JSON.stringify({session_id: session.id, revision: session.revision}),
      });
      if (!response.ok || !response.headers.get('Content-Type')?.startsWith('audio/mpeg'))
        throw new Error('Speech unavailable');
      const blob = await response.blob();
      if (generation !== this.generation) return;
      if (!blob.size || blob.size > 8 * 1024 * 1024) throw new Error('Invalid audio');
      this.unschedule(this.timer);
      this.timer = null;
      this.controller = null;
      this.url = this.urls.createObjectURL(blob);
      this.key = `${session.id}:${session.revision}`;
      this.audio.src = this.url;
      this.audio.onended = () => {
        if (generation !== this.generation) return;
        this.onStatus('Neural reply finished');
        this.onDone();
      };
      this.audio.onerror = () => {
        if (generation !== this.generation) return;
        this.onStatus('Audio playback failed. Try device voice.');
        this.onDone();
      };
      await this.play(generation);
    } catch {
      if (generation !== this.generation) return;
      this.cancel();
      this.onStatus('Neural speech unavailable. Text is still available; choose device voice or retry.');
      this.onDone();
    }
  }

  replay(session) {
    if (session.state === 'human') { this.cancel(); return; }
    if (this.controller && this.key === `${session.id}:${session.revision}`) return;
    if (this.url && this.key === `${session.id}:${session.revision}`) {
      this.audio.currentTime = 0;
      return this.play(this.generation); // Reuse this reply without another paid synthesis.
    }
    return this.speak(session);
  }
}
