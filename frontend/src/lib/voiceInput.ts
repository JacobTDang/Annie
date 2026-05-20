// Item #33 — Voice input via the browser's native SpeechRecognition API.
//
// We deliberately avoid pulling in transformers.js Whisper (~75 MB) for the
// MVP — the native API works in Chrome/Edge out of the box and produces
// usable transcripts for typical math/DSA prompts. Browsers without support
// (Firefox, Safari without speech) get a graceful "unsupported" message.

type SR = any; // SpeechRecognition is non-standard; the global is typed as `any`.

export interface VoiceRecognizer {
  start(): void;
  stop(): void;
  abort(): void;
  /** True while actively listening. */
  isListening(): boolean;
}

export interface VoiceRecognizerOptions {
  onTranscript: (text: string, isFinal: boolean) => void;
  onError: (message: string) => void;
  onEnd?: () => void;
  lang?: string;        // default "en-US"
  interim?: boolean;    // emit partial transcripts as you speak (default true)
}

function _getSRConstructor(): any | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

/** True if the current browser exposes SpeechRecognition. */
export function isVoiceInputSupported(): boolean {
  return _getSRConstructor() !== null;
}

/** Build a recognizer. Returns null if the browser doesn't support speech. */
export function createVoiceRecognizer(
  opts: VoiceRecognizerOptions,
): VoiceRecognizer | null {
  const Ctor = _getSRConstructor();
  if (!Ctor) return null;

  const rec: SR = new Ctor();
  rec.continuous = false;       // one shot — stops on first pause
  rec.interimResults = opts.interim ?? true;
  rec.lang = opts.lang ?? "en-US";

  let listening = false;

  rec.onresult = (evt: any) => {
    // Each result has multiple alternatives; concatenate the highest-confidence
    // transcript across all final results plus the latest interim.
    let finalText = "";
    let interimText = "";
    for (let i = evt.resultIndex; i < evt.results.length; i++) {
      const r = evt.results[i];
      if (r.isFinal) finalText += r[0].transcript;
      else interimText += r[0].transcript;
    }
    if (finalText) opts.onTranscript(finalText.trim(), true);
    else if (interimText) opts.onTranscript(interimText.trim(), false);
  };

  rec.onerror = (evt: any) => {
    listening = false;
    const msg = (evt && evt.error) ? String(evt.error) :
                "Voice input failed";
    opts.onError(msg);
  };

  rec.onend = () => {
    listening = false;
    opts.onEnd?.();
  };

  return {
    start() {
      if (listening) return;
      try { rec.start(); listening = true; }
      catch (e) {
        opts.onError(e instanceof Error ? e.message : String(e));
      }
    },
    stop() {
      if (!listening) return;
      try { rec.stop(); } catch { /* already stopped */ }
    },
    abort() {
      try { rec.abort(); } catch { /* ignore */ }
      listening = false;
    },
    isListening() { return listening; },
  };
}
