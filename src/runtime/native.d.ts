/** @noResolution @noSelf */
declare module "socket.core" {
  export function tcp(): BridgeSocket;
  export function gettime(): number;
}
interface BridgeSocket {
  settimeout(value: number): void;
  connect(host: string, port: number): LuaMultiReturn<[number | undefined, string | undefined]>;
  getpeername(): LuaMultiReturn<[string | undefined, number | undefined]>;
  send(data: string, from: number, to: number): LuaMultiReturn<[number | undefined, string | undefined, number | undefined]>;
  receive(bytes: number): LuaMultiReturn<[string | undefined, string | undefined, string | undefined]>;
  close(): void;
}
/** @noResolution @noSelf */
declare module "socketbridge_v4.dkjson" {
  const json: {
    null: object;
    encode(this: void, value: unknown): string;
    decode(this: void, value: string, position: number, nullValue: unknown): LuaMultiReturn<[unknown, number, string | undefined]>;
  };
  export = json;
}
declare const REPENTOGON: unknown;
declare const ModCallbacks: { [name: string]: number | undefined };
declare const SocketBridgeV4Config: { port?: number; token?: string; allowConsole?: boolean } | undefined;
