/** Capture mono 16 kHz PCM and wrap as WAV (no ffmpeg). */

const TARGET_RATE = 16000;

function writeString(view, offset, str) {
  for (let i = 0; i < str.length; i += 1) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

export function encodeWav(samples, sampleRate = TARGET_RATE) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i += 1) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function downsample(buffer, fromRate, toRate) {
  if (fromRate === toRate) return buffer;
  const ratio = fromRate / toRate;
  const newLen = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLen);
  for (let i = 0; i < newLen; i += 1) {
    const start = Math.floor(i * ratio);
    const end = Math.min(Math.floor((i + 1) * ratio), buffer.length);
    let sum = 0;
    let count = 0;
    for (let j = start; j < end; j += 1) {
      sum += buffer[j];
      count += 1;
    }
    result[i] = count ? sum / count : 0;
  }
  return result;
}

export class WavRecorder {
  constructor({ maxSeconds = 60, onTick } = {}) {
    this.maxSeconds = maxSeconds;
    this.onTick = onTick;
    this._ctx = null;
    this._stream = null;
    this._processor = null;
    this._source = null;
    this._chunks = [];
    this._startedAt = 0;
    this._timer = null;
    this.recording = false;
  }

  async start() {
    if (this.recording) return;
    this._stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    this._ctx = new AudioContext();
    this._source = this._ctx.createMediaStreamSource(this._stream);
    this._processor = this._ctx.createScriptProcessor(4096, 1, 1);
    this._chunks = [];
    this._processor.onaudioprocess = (ev) => {
      const input = ev.inputBuffer.getChannelData(0);
      this._chunks.push(new Float32Array(input));
    };
    this._source.connect(this._processor);
    this._processor.connect(this._ctx.destination);
    this._startedAt = performance.now();
    this.recording = true;
    this._timer = setInterval(() => {
      const elapsed = (performance.now() - this._startedAt) / 1000;
      if (this.onTick) this.onTick(elapsed);
      if (elapsed >= this.maxSeconds) {
        this.stop();
      }
    }, 200);
  }

  async stop() {
    if (!this.recording) return null;
    this.recording = false;
    if (this._timer) clearInterval(this._timer);
    this._timer = null;

    try {
      this._processor?.disconnect();
      this._source?.disconnect();
      await this._ctx?.close();
    } catch {
      /* ignore */
    }
    this._stream?.getTracks().forEach((t) => t.stop());

    const fromRate = this._ctx?.sampleRate || 44100;
    let length = 0;
    for (const c of this._chunks) length += c.length;
    const merged = new Float32Array(length);
    let offset = 0;
    for (const c of this._chunks) {
      merged.set(c, offset);
      offset += c.length;
    }
    const down = downsample(merged, fromRate, TARGET_RATE);
    this._chunks = [];
    this._ctx = null;
    this._stream = null;
    this._processor = null;
    this._source = null;
    return encodeWav(down, TARGET_RATE);
  }
}
