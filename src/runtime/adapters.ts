import type { Json, RecordValue } from "../protocol/types";
import { textValue } from "../protocol/validate";
import { array, encode, object } from "./codec";

export interface ModAdapter {
  version: string;
  ready?: (this: void) => boolean;
  observe?: { [method: string]: (this: void, params: RecordValue) => Json };
  invoke?: { [method: string]: (this: void, params: RecordValue) => Json };
}
export class Adapters {
  private entries = new LuaTable<string, ModAdapter>();
  register(id: string, adapter: ModAdapter): void {
    if (!textValue(id, 96) || !adapter || !textValue(adapter.version, 96)) throw new Error("Invalid adapter");
    if (this.entries.has(id)) throw new Error("Adapter already registered: " + id);
    this.entries.set(id, adapter);
  }
  unregister(id: string): void { this.entries.delete(id); }
  list(): RecordValue {
    const result: RecordValue = object({});
    for (const [id, adapter] of pairs(this.entries)) result[id] = adapter.version;
    return result;
  }
  private isReady(adapter: ModAdapter): boolean {
    if (adapter.ready === undefined) return true;
    const [ok, ready] = pcall(() => adapter.ready!());
    return ok && ready === true;
  }
  readiness(): RecordValue {
    const result: RecordValue = object({});
    for (const [id, adapter] of pairs(this.entries)) result[id] = this.isReady(adapter);
    return result;
  }
  call(id: string, method: string, params: RecordValue, mutating: boolean): Json {
    const adapter = this.entries.get(id);
    if (!adapter) throw new Error("MOD_ADAPTER_NOT_FOUND");
    if (!this.isReady(adapter)) throw new Error("MOD_NOT_READY");
    const fn = (mutating ? adapter.invoke : adapter.observe)?.[method];
    if (!fn) throw new Error("MOD_METHOD_NOT_FOUND");
    const result = fn(params);
    encode(result); // Reject unsupported userdata/cycles at the adapter boundary.
    return result;
  }
  expose(emit: (name: string, data: RecordValue) => void): void {
    const api: {
      version: number;
      register(this: void, id: string, adapter: ModAdapter): void;
      unregister(this: void, id: string): void;
      emit(this: void, name: string, data: RecordValue): void;
      array<T>(this: void, values?: T[]): T[];
      object<T extends object>(this: void, value: T): T;
    } = {
      version: 4,
      register: (id: string, adapter: ModAdapter) => this.register(id, adapter),
      unregister: (id: string) => this.unregister(id),
      emit: (name: string, data: RecordValue) => emit(name, data),
      array: <T>(values: T[] = []) => array(values),
      object: <T extends object>(value: T) => object(value),
    };
    (_G as unknown as { SocketBridgeV4: typeof api }).SocketBridgeV4 = api;
  }
}
