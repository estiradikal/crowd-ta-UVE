'use strict';

class CrowdAudioCaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const configuredSize = options.processorOptions && options.processorOptions.chunkSize;
    this.chunkSize = Number.isInteger(configuredSize) ? configuredSize : 4096;
    this.buffer = new Float32Array(this.chunkSize);
    this.position = 0;
  }

  process(inputs) {
    const channels = inputs[0];
    if (!channels || channels.length === 0) return true;
    const input = channels[0];
    let offset = 0;

    while (offset < input.length) {
      const count = Math.min(this.chunkSize - this.position, input.length - offset);
      this.buffer.set(input.subarray(offset, offset + count), this.position);
      this.position += count;
      offset += count;

      if (this.position === this.chunkSize) {
        const completed = this.buffer;
        this.port.postMessage(completed, [completed.buffer]);
        this.buffer = new Float32Array(this.chunkSize);
        this.position = 0;
      }
    }
    return true;
  }
}

registerProcessor('crowd-audio-capture', CrowdAudioCaptureProcessor);
