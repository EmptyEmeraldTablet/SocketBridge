export interface Pulse { requestId: string; playerIndex: number; action: number; value: number; ticks: number; startTick: number; }
export class InputController {
  private pulses: Pulse[] = [];
  add(pulse: Pulse): void {
    for (const existing of this.pulses) {
      if (existing.playerIndex === pulse.playerIndex && existing.action === pulse.action) throw new Error("Input action busy");
    }
    if (this.pulses.length >= 32) throw new Error("Input queue full");
    this.pulses.push(pulse);
  }
  value(playerIndex: number, action: number, hook: number, tick: number): number | boolean | undefined {
    for (const pulse of this.pulses) {
      if (pulse.playerIndex !== playerIndex || pulse.action !== action || tick < pulse.startTick || tick >= pulse.startTick + pulse.ticks) continue;
      if (hook === 0) return pulse.value > 0; // IS_ACTION_PRESSED
      if (hook === 1) return pulse.value > 0 && tick === pulse.startTick; // IS_ACTION_TRIGGERED
      if (hook === 2) return pulse.value; // GET_ACTION_VALUE
    }
    return undefined;
  }
  finishTick(tick: number): string[] {
    const completed: string[] = [];
    for (let i = this.pulses.length - 1; i >= 0; i--) {
      const pulse = this.pulses[i];
      if (tick >= pulse.startTick + pulse.ticks - 1) { completed.push(pulse.requestId); this.pulses.splice(i, 1); }
    }
    return completed;
  }
  remove(requestId: string): void { this.pulses = this.pulses.filter(p => p.requestId !== requestId); }
  clear(): string[] { const ids = this.pulses.map(p => p.requestId); this.pulses = []; return ids; }
}
