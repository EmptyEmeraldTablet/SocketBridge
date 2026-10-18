export class StepController {
  paused = false;
  remaining = 0;
  requestId?: string;
  pause(): void { if (this.requestId !== undefined) throw new Error("Step in progress"); this.paused = true; }
  step(requestId: string, ticks: number): void {
    if (this.requestId !== undefined) throw new Error("Step in progress");
    this.paused = true; this.remaining = ticks; this.requestId = requestId;
  }
  blockUpdate(): boolean { return this.paused && this.remaining === 0; }
  afterUpdate(): string | undefined {
    if (this.requestId === undefined) return;
    this.remaining--;
    if (this.remaining === 0) { const id = this.requestId; this.requestId = undefined; return id; }
  }
  reset(): string | undefined { const id = this.requestId; this.requestId = undefined; this.remaining = 0; this.paused = false; return id; }
}
