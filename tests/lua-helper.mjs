import fs from "node:fs";
import { lua, lauxlib, lualib, to_luastring, to_jsstring } from "fengari";
export function runLua(driver, { entry = false, globals = "" } = {}) {
  let bundle = fs.readFileSync(new URL("../mod/main.lua", import.meta.url), "utf8");
  if (!entry) bundle = bundle.replace('local ____entry = require("runtime.bundleEntry", ...)\nreturn ____entry', '__sb_require = require');
  const vendor = fs.readFileSync(new URL("../vendor/dkjson.lua", import.meta.url), "utf8");
  const L = lauxlib.luaL_newstate(); lualib.luaL_openlibs(L);
  const chunks = [
    `package.preload["socketbridge_v4.dkjson"] = function()\n${vendor}\nend\n${globals}\nfunction new(class, ...) local o = setmetatable({}, class.prototype); o:____constructor(...); return o end`,
    bundle, driver,
  ];
  try {
    for (const [i, chunk] of chunks.entries()) {
      const status = lauxlib.luaL_dostring(L, to_luastring(chunk));
      if (status !== lua.LUA_OK) {
        const message = lua.lua_tostring(L, -1);
        throw new Error(`Lua chunk ${i}: ${message ? to_jsstring(message) : "non-string error"}`);
      }
    }
  } finally { lua.lua_close(L); }
}
export const fakeSocketLua = `
function makeSocket()
  return {
    incoming = {}, output = "", sendLimit = 1000000, peer = true, connectError = nil,
    settimeout = function(self, timeout) assert(timeout == 0) end,
    connect = function(self) if self.connectError then return nil, self.connectError end return 1 end,
    getpeername = function(self) if self.peer then return "127.0.0.1", 9527 end return nil end,
    send = function(self, data, from, ending)
      local last = math.min(ending, from + self.sendLimit - 1)
      self.output = self.output .. string.sub(data, from, last)
      if last < ending then return nil, "timeout", last end
      return last
    end,
    receive = function(self)
      local part = table.remove(self.incoming, 1)
      if part then return nil, "timeout", part end
      return nil, "timeout", ""
    end,
    close = function(self) self.closed = true end,
  }
end
`;
