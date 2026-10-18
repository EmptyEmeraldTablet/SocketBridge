# SocketBridge v4

A TypeScript/TypeScriptToLua bridge for observing and testing Isaac mod logic under REPENTOGON. The Node SDK uses explicit request IDs, authoritative snapshots, bounded nonblocking transport, update stepping, finite input pulses, structured events and mod-specific adapters.

Build with `npm ci` and `npm run check`. With the game closed, install the `mod/` artifact using `npm run deploy`; it backs up the existing installation. Start the host with `npm run serve`, then launch REPENTOGON. The bridge does not automatically start a game run.

On the verified REPENTOGON 1.1.3 installation, launch with `--luadebug` to enable `socket.core`. Transport readiness at the menu does not imply gameplay readiness: use `waitForRuntime({ inGame: true, adapters: ["your-mod"] })`. Adapters can expose a `ready()` predicate for their own initialization. REPENTOGON's `[VanillaTweaks] SkipIntro=1` skips the opening cutscene without starting a run.

See [the current README](README.md), [design](docs/V4_DESIGN.md), and [validation](docs/VALIDATION.md). Old Python tools use v3 and cannot control v4. Historical documentation is retained in [legacy/README_EN.v3.md](legacy/README_EN.v3.md).
