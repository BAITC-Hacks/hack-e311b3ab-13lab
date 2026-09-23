// Converts captured audio to 16-bit PCM in ~100 ms chunks for the live session.
// The AudioContext runs at 16 kHz, so no resampling is needed here.
class PcmWriter extends AudioWorkletProcessor {
  constructor() {
    super()
    this.chunk = new Int16Array(1600)
    this.length = 0
    this.energy = 0
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0]
    if (!channel) return true
    for (let index = 0; index < channel.length; index++) {
      const sample = Math.max(-1, Math.min(1, channel[index]))
      this.energy += sample * sample
      this.chunk[this.length++] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
      if (this.length === this.chunk.length) {
        const level = Math.sqrt(this.energy / this.length)
        this.port.postMessage({ pcm: this.chunk.buffer, level }, [this.chunk.buffer])
        this.chunk = new Int16Array(1600)
        this.length = 0
        this.energy = 0
      }
    }
    return true
  }
}

registerProcessor('pcm-writer', PcmWriter)
