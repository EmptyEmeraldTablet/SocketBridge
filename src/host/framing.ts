import { MAX_BUFFER_BYTES, MAX_LINE_BYTES } from "../protocol/types.js";

/** Buffer bytes before decoding UTF-8: multibyte sequences may straddle TCP chunks. */
export class JsonLines {
  private buffer = Buffer.alloc(0);
  feed(chunk: Buffer): unknown[] {
    if (this.buffer.length + chunk.length > MAX_BUFFER_BYTES) throw new Error("RX buffer exceeded");
    this.buffer = Buffer.concat([this.buffer, chunk]);
    const messages: unknown[] = [];
    let end: number;
    while ((end = this.buffer.indexOf(10)) >= 0) {
      if (end > MAX_LINE_BYTES) throw new Error("Message too large");
      const bytes = this.buffer.subarray(0, end);
      this.buffer = this.buffer.subarray(end + 1);
      if (bytes.length === 0) continue;
      const line = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      messages.push(JSON.parse(line));
    }
    if (this.buffer.length > MAX_LINE_BYTES) throw new Error("Unterminated message too large");
    return messages;
  }
}
