import { createWriteStream, mkdirSync, type WriteStream } from "node:fs";
import path from "node:path";
import type { BridgeServer } from "./server.js";

export class Recorder {
  private stream: WriteStream;
  private failure?: Error;
  private onRecord: (entry: unknown) => void;
  private lifecycle: [string, (value: unknown) => void][] = [];
  private closing?: Promise<void>;
  private fail(error: Error): void {
    if (this.failure) return;
    this.failure = error;
    this.bridge.emit("fault", error);
    // Missing evidence invalidates the run; disconnect also releases game control.
    void this.bridge.close().catch(() => {});
  }
  constructor(private bridge: BridgeServer, file: string) {
    mkdirSync(path.dirname(file), { recursive: true });
    this.stream = createWriteStream(file, { flags: "wx" });
    this.stream.on("error", error => this.fail(error));
    this.onRecord = entry => {
      if (this.failure) return;
      if (this.stream.writableLength > 4 * 1024 * 1024) {
        this.fail(new Error("Recorder backpressure limit; recording incomplete")); return;
      }
      this.stream.write(JSON.stringify({ at: new Date().toISOString(), monotonicNs: process.hrtime.bigint().toString(), entry }) + "\n");
    };
    bridge.on("record", this.onRecord);
    for (const event of ["connection", "disconnect", "fault", "closed"]) {
      const listener = (value: unknown) => this.onRecord({ lifecycle: event, value: value instanceof Error ? value.message : value });
      this.lifecycle.push([event, listener]); bridge.on(event, listener);
    }
  }
  close(): Promise<void> { return this.closing ??= this.finish(); }
  private async finish(): Promise<void> {
    this.bridge.off("record", this.onRecord);
    for (const [event, listener] of this.lifecycle) this.bridge.off(event, listener);
    if (this.stream.destroyed) { if (this.failure) throw this.failure; return; }
    await new Promise<void>((resolve, reject) => {
      this.stream.once("error", reject);
      this.stream.end(() => resolve());
    });
    if (this.failure) throw this.failure;
  }
}
