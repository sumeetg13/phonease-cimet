/* Conversational pacing for browser TTS. Voice quality depends on installed voices. */
export default class ConversationalVoice {
    constructor({synthesis, Utterance, onDone = () => {},
      schedule = (fn, ms) => setTimeout(fn, ms), unschedule = id => clearTimeout(id)}) {
      this.synthesis = synthesis;
      this.onDone = onDone; // The caller's turn: fired only when a reply finishes on its own.
      this.Utterance = Utterance;
      this.schedule = schedule;
      this.unschedule = unschedule;
      this.generation = 0;
      this.timer = null;
      this.current = null;
    }

    cancel() {
      // Invalidate callbacks as well as queued timers: cancel() can fire onend/onerror.
      this.generation += 1;
      if (this.timer !== null) this.unschedule(this.timer);
      this.timer = null;
      this.current = null;
      if (this.synthesis) this.synthesis.cancel();
    }

    static phrases(text) {
      // Keep punctuation for native intonation; pause explicitly at sentence/list boundaries.
      return (text.match(/[^.!?;]+(?:[.!?;]+|$)/g) || [])
        .map(part => part.trim()).filter(Boolean);
    }

    chooseVoice() {
      const voices = this.synthesis.getVoices().filter(v => /^en[-_]/i.test(v.lang));
      const score = v => (/^en[-_]AU$/i.test(v.lang) ? 12 : /^en[-_]GB$/i.test(v.lang) ? 6 : 2)
        + (/natural|neural|enhanced|premium/i.test(v.name) ? 8 : 0)
        + (v.default ? 1 : 0);
      return voices.sort((a, b) => score(b) - score(a))[0] || null;
    }

    speak(text) {
      this.cancel();
      if (!this.synthesis || !this.Utterance) return;
      const phrases = ConversationalVoice.phrases(text);
      const generation = this.generation;
      const reassuring = /sorry|frustrat|specialist|didn't catch/i.test(text);
      const next = index => {
        if (generation !== this.generation || index >= phrases.length) return;
        this.timer = null;
        const phrase = phrases[index];
        const utterance = new this.Utterance(phrase);
        this.current = utterance; // Keep a reference until the browser has finished.
        const voice = this.chooseVoice();
        if (voice) utterance.voice = voice;
        utterance.lang = voice ? voice.lang : 'en-AU';
        const question = /\?$/.test(phrase);
        // Gentle modulation, not random pitch jumps or artificial filler words.
        utterance.rate = reassuring ? 0.84 : question ? 0.86 : 0.89;
        utterance.pitch = reassuring ? 0.98 : question ? 1.04 : index === 0 ? 1.01 : 0.99;
        utterance.volume = 1;
        utterance.onend = () => {
          if (generation !== this.generation) return;
          this.current = null;
          if (index + 1 < phrases.length) {
            const pause = /;$/.test(phrase) ? 300 : /\?$/.test(phrase) ? 650 : 520;
            this.timer = this.schedule(() => next(index + 1), pause);
          } else this.onDone();
        };
        utterance.onerror = () => {
          if (generation === this.generation) this.cancel();
        };
        this.synthesis.speak(utterance);
      };
      // Let the caller finish and give the reply a short, conversational beat.
      if (phrases.length) this.timer = this.schedule(() => next(0), 700);
      else this.onDone();
    }
  }
