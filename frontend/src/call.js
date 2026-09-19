/* Hands-free call turn-taking: one continuous microphone stream, live captions, and
   silence endpointing, so the caller speaks and listens instead of pressing a button. */
export default class Call {
  constructor({Recognition, onCaption = () => {}, onFinal = () => {}, onStage = () => {}, onError = () => {},
    schedule = (fn, ms) => setTimeout(fn, ms), unschedule = id => clearTimeout(id),
    silence = 1200, lang = 'en-AU'}) {
    Object.assign(this, {Recognition, onCaption, onFinal, onStage, onError, schedule, unschedule, silence, lang});
    this.active = false;      // The call is up: the mic reopens after every assistant reply.
    this.listening = false;
    this.recognition = null;
    this.timer = null;
    this.pending = '';        // Final words waiting for the caller to finish the sentence.
    this.confidence = null;
    this.generation = 0;      // Invalidates callbacks of a recognition we have abandoned.
  }

  get supported() {
    return !!this.Recognition;
  }

  open() {
    if (!this.supported) {
      this.onError('Speech recognition is unavailable in this browser. The call continues as text.');
      return false;
    }
    this.active = true;
    this.onStage('connecting');
    return true;
  }

  close() {
    this.active = false;
    this.hold();
    this.onStage('');
  }

  // Close the microphone for one turn: the assistant answers before the caller is heard again.
  hold() {
    this.generation += 1;
    if (this.timer !== null) this.unschedule(this.timer);
    this.timer = null;
    this.pending = '';
    this.confidence = null;
    const recognition = this.recognition;
    this.recognition = null;
    this.listening = false;
    this.onCaption('');
    recognition?.abort();
    if (this.active) this.onStage('holding');
  }

  listen() {
    if (!this.active || this.listening || !this.supported) return;
    const generation = this.generation;
    const recognition = new this.Recognition();
    recognition.lang = this.lang;
    recognition.continuous = true;      // Keep one stream open across pauses, like an open line.
    recognition.interimResults = true;  // Words appear while they are spoken.
    recognition.maxAlternatives = 1;
    this.recognition = recognition;
    this.listening = true;
    recognition.onstart = () => {
      if (generation === this.generation) this.onStage('listening');
    };
    recognition.onresult = event => {
      if (generation === this.generation) this.collect(event);
    };
    recognition.onerror = event => {
      if (generation !== this.generation) return;
      // Chrome routinely ends an idle stream; that is a pause in a call, not a failure.
      if (event.error === 'no-speech' || event.error === 'aborted') return;
      this.onError('Microphone: ' + event.error + '. You can still type a reply.');
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') this.close();
    };
    recognition.onend = () => {
      if (generation !== this.generation) return;
      this.listening = false;
      if (this.pending.trim()) return this.flush();
      if (this.active) this.listen();   // Reopen the line the browser closed on its own.
    };
    try {
      recognition.start();
    } catch {
      this.listening = false;           // Already running: the existing stream stays in place.
    }
  }

  collect(event) {
    let interim = '';
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index], best = result[0];
      if (result.isFinal) {
        this.pending = (this.pending + ' ' + best.transcript).trim();
        if (best.confidence > 0) this.confidence = best.confidence;
      } else interim += best.transcript;
    }
    this.onCaption((this.pending + ' ' + interim).trim());
    if (this.timer !== null) this.unschedule(this.timer);
    this.timer = null;
    // Send only once the caller has paused, so one sentence is never split across two turns.
    if (this.pending.trim() && !interim.trim()) this.timer = this.schedule(() => this.flush(), this.silence);
  }

  flush() {
    if (this.timer !== null) this.unschedule(this.timer);
    this.timer = null;
    const text = this.pending.trim(), confidence = this.confidence;
    if (!text) {
      this.onCaption('');
      return;
    }
    this.hold();
    this.onStage('thinking');
    this.onFinal(text, confidence);
  }
}
