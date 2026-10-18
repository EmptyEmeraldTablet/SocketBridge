/** Copy into a mod's DEBUG build only. Register after both mods are loaded. */
import type { ModAdapter } from "../src/runtime/adapters";
declare const SocketBridgeV4: {
  register(this: void, id: string, adapter: ModAdapter): void;
  unregister(this: void, id: string): void;
  emit(this: void, name: string, data: { [key: string]: number | string }): void;
};

// Replace these with actual business state. Observe functions must not change that state.
let activationCount = 0;
let initialized = false;
// Wire these to the target mod's own initialization/teardown, after its business setup finishes.
export function onBusinessInitialized(): void { initialized = true; }
export function onBusinessExited(): void { initialized = false; }
export function onActualBusinessActivation(): void {
  activationCount++;
  SocketBridgeV4.emit("example.activated", { activationCount });
}
export function registerDebugAdapter(): void {
  SocketBridgeV4.register("example-mod", {
    version: "1",
    ready: () => initialized,
    observe: { counters: () => ({ activationCount }) },
    invoke: { resetFixture: () => { activationCount = 0; return { reset: true }; } },
  });
}
// Call registerDebugAdapter from REPENTOGON MC_POST_MODS_LOADED after checking the API exists.
// TS calls are dot calls: the public bridge functions explicitly have `this: void`.
// Test natural actions through input.pulse / runtime.step; do not replace business execution
// with resetFixture, and do not ship the debug adapter in release builds.
