# Lua JSON dependency

`dkjson.lua` is dkjson 2.5 by David Heiko Kolf, retained with its MIT license header.

Source: https://github.com/LuaDist/dkjson/blob/master/dkjson.lua (retrieved 2026-10-05).

It is vendored and hashed by the build, so runtime does not download code. The module's default object/array metatables preserve the distinction between `{}` and `[]`, including empty values. `src/runtime/codec.ts` validates serializable values and nesting and uses this module without registering a global `json` table. The game-bundled parser is not modified.
