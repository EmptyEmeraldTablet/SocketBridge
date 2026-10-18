import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { runLua, fakeSocketLua } from "./lua-helper.mjs";

test("compiled Lua preserves object/array/null and UTF-8; command validation agrees on empty args", () => {
  runLua(String.raw`
    local codec = __sb_require("runtime.codec")
    local validate = __sb_require("protocol.validate").validateCommand
    local json = require("socketbridge_v4.dkjson")
    local data = codec.decode(nil, '{"a":[],"o":{},"n":null,"label":"\\u4ee5\\u6492"}')
    assert(codec.isList(nil, data.a) and not codec.isRecord(nil, data.a))
    assert(codec.isRecord(nil, data.o) and not codec.isList(nil, data.o))
    assert(data.n == json.null and data.label == "以撒")
    local cmd = codec.decode(nil, '{"method":"runtime.pause","args":{},"timeoutMs":1000}')
    assert(validate(nil, cmd, codec.isRecord, codec.isList) == nil)
    cmd.args = codec.array(nil, {})
    assert(validate(nil, cmd, codec.isRecord, codec.isList) ~= nil)
    assert(codec.encode(nil, codec.array(nil, {})) == "[]")
    assert(codec.encode(nil, codec.object(nil, {})) == "{}")
    local cycle = {}; cycle.x = cycle
    assert(not pcall(codec.encode, nil, cycle))
    assert(not pcall(codec.decode, nil, '{} trailing'))
  `);
});

test("Lua transport retains receive partials and sends only unsent suffixes", () => {
  runLua(String.raw`${fakeSocketLua}
    local Transport = __sb_require("runtime.transport").Transport
    local socket = makeSocket(); socket.sendLimit = 3
    local lines, connects, closes = {}, 0, 0
    local transport = new(Transport, function() return socket end, 9527, {
      connected = function() connects = connects + 1 end,
      disconnected = function() closes = closes + 1 end,
      line = function(_, s) table.insert(lines, s) end,
    })
    transport:pump(0)
    assert(connects == 1)
    assert(transport:enqueue('1234567'))
    socket.incoming = {'{"a":', '1}\n{"b":2}\n'}
    transport:pump(1); assert(#lines == 0)
    transport:pump(2); transport:pump(3)
    assert(#lines == 2 and lines[1] == '{"a":1}' and lines[2] == '{"b":2}')
    assert(socket.output == '1234567\n' and transport.queuedBytes == 0)
    assert(closes == 0)
  `);
});

test("connect returned failure is not success; async connection waits for peer", () => {
  runLua(String.raw`${fakeSocketLua}
    local Transport = __sb_require("runtime.transport").Transport
    local socket = makeSocket(); socket.connectError = "refused"
    local connects = 0
    local transport = new(Transport, function() return socket end, 9527, {
      connected = function() connects = connects + 1 end, disconnected = function() end, line = function() end
    })
    transport:pump(0); assert(connects == 0 and socket.closed)
    socket = makeSocket(); socket.connectError = "timeout"; socket.peer = false
    transport:pump(1000); assert(connects == 0)
    socket.peer = true; transport:pump(1001); assert(connects == 1)
  `);
});

test("transport bounds unterminated payloads and output pressure", () => {
  runLua(String.raw`${fakeSocketLua}
    local socket = makeSocket(); local closed = false
    local T = __sb_require("runtime.transport").Transport
    local t = new(T, function() return socket end, 9527, {connected=function() end, disconnected=function() closed=true end,line=function() end})
    t:pump(0)
    for i=1,65 do socket.incoming[1]=string.rep("x",4096); t:pump(i) end
    assert(closed and socket.closed)
  `);
});

test("input uses stable same-tick edge, finite duration, per-player isolation", () => {
  runLua(String.raw`
    local C = __sb_require("runtime.input").InputController
    local i = new(C)
    i:add({requestId="p",playerIndex=0,action=4,value=1,ticks=2,startTick=10})
    assert(i:value(0,4,1,9) == nil)
    assert(i:value(0,4,1,10) == true and i:value(0,4,1,10) == true)
    assert(i:value(0,4,1,11) == false and i:value(0,4,0,11) == true)
    assert(i:value(1,4,0,10) == nil)
    assert(#i:finishTick(10) == 0)
    assert(i:finishTick(11)[1] == "p" and i:value(0,4,0,12) == nil)
  `);
});

test("step budget consumes actual post updates, never cancelled pre updates", () => {
  runLua(String.raw`
    local s = new(__sb_require("runtime.scheduler").StepController)
    s:step("r",2)
    for i=1,10 do assert(s:blockUpdate() == false) end
    assert(s.remaining == 2)
    assert(s:afterUpdate() == nil and s.remaining == 1)
    assert(s:afterUpdate() == "r" and s:blockUpdate())
    s:reset(); assert(not s:blockUpdate())
  `);
});

test("snapshot empty collection is authoritative; unsupported is not zero", () => {
  runLua(String.raw`
    Isaac = { GetRoomEntities = function() return {} end }
    local engine = new(__sb_require("runtime.engine").Engine); engine.inGame = true
    local clock = {runEpoch=1,roomEpoch=2,updateTick=3,renderTick=4}
    local snapshot = engine:snapshot({"pickups","missing"}, clock)
    assert(snapshot.complete == false and snapshot.sensors.missing.status == "unsupported")
    assert(snapshot.sensors.pickups.status == "ok")
    local encoded = __sb_require("runtime.codec").encode(nil, snapshot)
    assert(string.find(encoded,'"data":[]',1,true))
    engine.inGame = false
    assert(engine:snapshot({"players"}, clock).sensors.players.status == "error")
  `);
});

test("inventory discovers mod items beyond 733 and records true counts/effects separately", () => {
  runLua(String.raw`
    GetPtrHash = function() return 10 end
    local p = {InitSeed=7,Exists=function() return true end,GetPlayerType=function() return 0 end,
      GetCollectibleNum=function(_, id, real) assert(real); return id==900 and 2 or 0 end,
      GetEffects=function() return {GetCollectibleEffectNum=function(_,id) return id==901 and 1 or 0 end} end,
      GetCollectibleCount=function() return 2 end,GetTrinket=function() return 0 end,
      GetCard=function() return 0 end,GetPill=function() return 0 end,GetActiveItem=function() return 0 end,
      GetActiveCharge=function() return 0 end,GetBatteryCharge=function() return 0 end}
    Game=function() return {GetNumPlayers=function() return 1 end} end
    Isaac={GetPlayer=function() return p end,GetItemConfig=function() return {
      GetCollectibles=function() return {Size=902} end,GetCollectible=function(_,id) return {} end} end}
    local engine = new(__sb_require("runtime.engine").Engine); engine.inGame=true
    local s=engine:snapshot({"inventory"},{updateTick=1})
    assert(s.complete, s.sensors.inventory.error)
    assert(s.sensors.inventory.data[1].collectibles["900"]==2)
    assert(s.sensors.inventory.data[1].collectibleEffects["901"]==1)
  `);
});

test("compiled runtime correlates results, deduplicates effects, pauses and clears control on disconnect", () => {
  runLua(String.raw`${fakeSocketLua}
    local codec=__sb_require("runtime.codec")
    local Runtime=__sb_require("runtime.bridge").RuntimeBridge
    local socket=makeSocket(); local now=0
    REPENTOGON=true; ModCallbacks={MC_PRE_UPDATE=1026}
    local bridge=new(Runtime,{port=9527,token="test",allowConsole=false,buildId="fixture"},function() return socket end,function() return now end)
    bridge:pump()
    socket.incoming={codec.encode(nil,{protocol="socketbridge/4",kind="welcome",sessionId="s",connectionId="c",seq=1,payload={}}).."\n"}
    bridge:pump(); bridge:gameStarted(false)
    local seq=1
    function send(id,method,args)
      seq=seq+1
      socket.incoming={codec.encode(nil,{protocol="socketbridge/4",kind="command",sessionId="s",connectionId="c",seq=seq,requestId=id,runEpoch=bridge.runEpoch,roomEpoch=bridge.roomEpoch,
        payload={method=method,args=args,timeoutMs=1000}}).."\n"}
      bridge:pump()
    end
    local effects=0
    bridge.adapters:register("test",{version="1",invoke={inc=function() effects=effects+1; return {count=effects} end}})
    send("a","mod.invoke",{modId="test",name="inc",params={}}); bridge:preUpdate()
    send("a","mod.invoke",{modId="test",name="inc",params={}}); bridge:preUpdate()
    assert(effects==1)
    send("p","runtime.pause",{}); assert(bridge:preUpdate()==true)
    send("step","runtime.step",{ticks=2})
    bridge:preUpdate(); bridge:postUpdate(); bridge:preUpdate(); bridge:postUpdate()
    assert(bridge.steps.paused and bridge.steps.remaining==0)
    bridge.transport:close("test"); assert(not bridge.steps.paused)
    assert(string.find(socket.output,'"requestId":"a"',1,true))
  `);
});

test("command fingerprint ignores object order and decoder refuses excessive nesting", () => {
  runLua(String.raw`
    local c=__sb_require("runtime.codec")
    assert(c.canonical(nil,c.decode(nil,'{"x":1,"y":{"b":2,"a":3}}'))==c.canonical(nil,c.decode(nil,'{"y":{"a":3,"b":2},"x":1}')))
    assert(not pcall(c.decode,nil,string.rep("[",33).."0"..string.rep("]",33)))
  `);
});

test("main registers callbacks with correct hidden self and no definitions/common runtime imports", () => {
  const lua = fs.readFileSync(new URL("../mod/main.lua", import.meta.url), "utf8");
  assert.doesNotMatch(lua, /require\("isaac-typescript-definitions|require\("isaacscript-common/);
  runLua(String.raw`
    assert(callbacks[15] and callbacks[1026] and callbacks[1006])
    callbacks[15](modObject, false)
    assert(SocketBridgeV4.version == 4)
    local called=false
    SocketBridgeV4.register("public-api",{version="1",observe={state=function(params) called=true; return {} end}})
  `, { entry: true, globals: `${fakeSocketLua}
    Isaac={DebugString=function() end}
    REPENTOGON=true; ModCallbacks={MC_PRE_UPDATE=1026,MC_POST_ENTITY_TAKE_DMG=1006,MC_MAIN_MENU_RENDER=1023}
    callbacks={}; modObject={AddCallback=function(_,id,fn) callbacks[id]=fn end}
    RegisterMod=function() return modObject end
    package.preload["socket.core"]=function() return {tcp=function() return makeSocket() end,gettime=function() return 0 end} end
    package.preload["socketbridge_v4.config"]=function() return {port=9527,token="test",allowConsole=false} end
  ` });
});

test("menu commands fail immediately and exiting a run invalidates world epochs", () => {
  runLua(String.raw`${fakeSocketLua}
    REPENTOGON=true; ModCallbacks={MC_PRE_UPDATE=1026}
    local c=__sb_require("runtime.codec")
    local socket=makeSocket()
    local b=new(__sb_require("runtime.bridge").RuntimeBridge,{port=9527,token="test",allowConsole=false,buildId="fixture"},function() return socket end,function() return 0 end)
    b:pump()
    socket.incoming={c.encode(nil,{protocol="socketbridge/4",kind="welcome",sessionId="s",connectionId="c",seq=1,payload={}}).."\n"}
    b:pump()
    socket.incoming={c.encode(nil,{protocol="socketbridge/4",kind="command",sessionId="s",connectionId="c",seq=2,runEpoch=0,roomEpoch=0,requestId="menu",
      payload={method="state.snapshot",args={sensors={"players"}},timeoutMs=1000}}).."\n"}
    b:pump(); assert(string.find(socket.output,'"code":"NOT_IN_GAME"',1,true))
    b:gameStarted(false); local epoch=b.roomEpoch
    b:gameExit(); assert(not b.engine.inGame and b.roomEpoch==epoch+1)
  `);
});

test("adapter readiness follows target initialization and guards calls before it", () => {
  runLua(String.raw`
    local a=new(__sb_require("runtime.adapters").Adapters)
    local initialized=false; local calls=0
    a:register("target",{version="1",ready=function(...) assert(select("#",...)==0); return initialized end,
      observe={state=function(params) assert(params.key=="value"); calls=calls+1; return {} end}})
    assert(a:readiness().target==false)
    assert(not pcall(a.call,a,"target","state",{key="value"},false) and calls==0)
    initialized=true
    assert(a:readiness().target==true)
    a:call("target","state",{key="value"},false); assert(calls==1)
    initialized=false; assert(a:readiness().target==false)
  `);
});
