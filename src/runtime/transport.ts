import type {} from "isaac-typescript-definitions";

export interface TransportHooks {
  connected(): void;
  disconnected(reason: string): void;
  line(value: string): void;
}
/** Byte-oriented LuaSocket pump, no blocking waits inside game callbacks. */
export class Transport {
  private socket?: BridgeSocket;
  private connecting = false;
  private active = false;
  private connectAt = 0;
  private retryAt = 0;
  private rx = "";
  private tx: string[] = [];
  private txOffset = 1;
  private queuedBytes = 0;
  constructor(private factory: () => BridgeSocket, private port: number, private hooks: TransportHooks) {}
  get connected(): boolean { return this.active; }
  get pendingBytes(): number { return this.queuedBytes; }
  enqueue(line: string): boolean {
    if (!this.active) return false;
    if (line.length > 262144 || this.queuedBytes + line.length + 1 > 1048576 || this.tx.length >= 256) {
      this.close("TX_LIMIT"); return false;
    }
    this.tx.push(line + "\n"); this.queuedBytes += line.length + 1;
    return true;
  }
  close(reason: string): void {
    const hadSocket = this.socket !== undefined;
    if (this.socket) pcall(() => this.socket!.close());
    this.socket = undefined; this.active = false; this.connecting = false;
    this.rx = ""; this.tx = []; this.txOffset = 1; this.queuedBytes = 0;
    if (hadSocket) this.hooks.disconnected(reason);
  }
  pump(now: number): void {
    const [ok, issue] = pcall(() => this.process(now));
    if (!ok) this.close("SOCKET_EXCEPTION: " + tostring(issue));
  }
  private process(now: number): void {
    if (!this.socket) {
      if (now < this.retryAt) return;
      this.retryAt = now + 1000;
      this.socket = this.factory();
      this.socket.settimeout(0);
      const [connected, err] = this.socket.connect("127.0.0.1", this.port);
      if (connected !== undefined) this.activate();
      else if (err === "timeout" || err === "Operation already in progress") { this.connecting = true; this.connectAt = now; }
      else { this.close("CONNECT: " + tostring(err)); return; }
    }
    if (this.connecting) {
      const [address] = this.socket!.getpeername();
      if (address !== undefined) this.activate();
      else if (now - this.connectAt > 2000) this.close("CONNECT_TIMEOUT");
    }
    if (!this.active || !this.socket) return;
    let lines = 0;
    // Consume buffered complete lines before requesting more bytes.
    const consume = () => {
      while (lines < 32) {
        const [ending] = string.find(this.rx, "\n", 1, true);
        if (ending === undefined) break;
        const line = string.sub(this.rx, 1, ending - 1);
        this.rx = string.sub(this.rx, ending + 1);
        lines++;
        if (line.length > 262144) error("RX_LINE_LIMIT");
        if (line.length > 0) this.hooks.line(line);
        if (!this.active) return;
      }
    };
    consume();
    for (let i = 0; i < 8 && lines < 32 && this.active; i++) {
      const [data, err, partial] = this.socket!.receive(4096);
      this.rx += data ?? partial ?? "";
      if (this.rx.length > 1048576) error("RX_BUFFER_LIMIT");
      consume();
      if (!this.active) return;
      if (err === "closed") { this.close("EOF"); return; }
      if (err !== undefined && err !== "timeout") { this.close("RECEIVE: " + err); return; }
      if (err === "timeout") break;
    }
    const [newline] = string.find(this.rx, "\n", 1, true);
    if (newline === undefined && this.rx.length > 262144) error("RX_LINE_LIMIT");
    let remaining = 32768;
    while (remaining > 0 && this.tx.length > 0 && this.active) {
      const line = this.tx[0];
      const ending = math.min(line.length, this.txOffset + remaining - 1);
      const [last, err, partial] = this.socket!.send(line, this.txOffset, ending);
      const sentTo = last ?? partial ?? this.txOffset - 1;
      if (sentTo < this.txOffset - 1 || sentTo > ending) error("Invalid send cursor");
      const sent = sentTo - this.txOffset + 1;
      this.txOffset = sentTo + 1; remaining -= sent; this.queuedBytes -= sent;
      if (this.txOffset > line.length) { table.remove(this.tx, 1); this.txOffset = 1; }
      if (err !== undefined && err !== "timeout") { this.close("SEND: " + err); return; }
      if (err === "timeout" || sent === 0) break;
    }
  }
  private activate(): void { this.active = true; this.connecting = false; this.hooks.connected(); }
}
