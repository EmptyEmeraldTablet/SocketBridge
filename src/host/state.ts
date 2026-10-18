import type { Clock, SensorResult, Snapshot } from "../protocol/types.js";

/** Observational cache only. Tests request fresh snapshots instead of inferring absence by TTL. */
export class StateStore {
  private epoch = "";
  private clock?: Clock;
  private values = new Map<string, SensorResult>();
  clear(): void { this.epoch = ""; this.clock = undefined; this.values.clear(); }
  observeClock(clock: Clock): void {
    if (this.clock && (clock.runEpoch < this.clock.runEpoch || clock.roomEpoch < this.clock.roomEpoch)) return;
    const epoch = `${clock.runEpoch}:${clock.roomEpoch}`;
    if (epoch !== this.epoch) { this.values.clear(); this.epoch = epoch; }
    this.clock = clock;
  }
  apply(snapshot: Snapshot): void {
    if (this.clock && (snapshot.runEpoch < this.clock.runEpoch || snapshot.roomEpoch < this.clock.roomEpoch)) return;
    this.observeClock(snapshot);
    for (const [name, result] of Object.entries(snapshot.sensors)) {
      const previous = this.values.get(name);
      if (!previous || result.sampleTick >= previous.sampleTick) this.values.set(name, result);
    }
  }
  get(name: string, currentTick: number, maxAgeTicks: number): SensorResult | undefined {
    const value = this.values.get(name);
    if (!value || currentTick < value.sampleTick || currentTick - value.sampleTick > maxAgeTicks) return undefined;
    return value;
  }
}
