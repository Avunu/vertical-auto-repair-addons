/* eslint-disable */
/**
 * GENERATED - do not edit. Source: repair_tech_api/frontend/client.ts,
 * via repair_tech_api/tools/generate_api_types.mjs. Regenerate with
 * `pnpm run generate`.
 */
/**
 * The typed facade client. tools/generate_api_types.mjs copies this file next
 * to the `api.d.ts` it generates (which exports `Api`, the map of model ->
 * method -> {params, result}), so every frontend gets the same client typed
 * against its own facades:
 *
 *     const odoo = createClient({transport: transportFor(serverVersion)});
 *     const job = await odoo.call("repair.tech.app", "job", {repair_id: 7});
 *     //    ^? JobDetail, from the Pydantic return annotation
 *     await odoo.call("repair.tech.app", "job", {});  // tsc error: repair_id
 *
 * Two transports, one contract. Facades are `@api.model` methods taking only
 * keyword arguments, so on 17.0/18.0 they go through JSON-RPC's call_kw with
 * `args: []`, and on 19.0+ through JSON-2, which posts the keyword arguments
 * as the body. Same origin either way: the Odoo session cookie authenticates,
 * and nothing here handles credentials unless an API key is passed.
 */
import type {Api} from "./api";

export type Model = keyof Api & string;
export type Method<M extends Model> = keyof Api[M] & string;

type Spec<M extends Model, F extends Method<M>> = Api[M][F] extends {
  params: infer P;
  result: infer R;
}
  ? {params: P; result: R}
  : never;

export type Params<M extends Model, F extends Method<M>> = Spec<M, F>["params"];
export type Result<M extends Model, F extends Method<M>> = Spec<M, F>["result"];

/** A facade without required arguments may be called without a params object. */
export type ParamsArg<M extends Model, F extends Method<M>> =
  Record<never, never> extends Params<M, F>
    ? [params?: Params<M, F>]
    : [params: Params<M, F>];

/** What went wrong, in the terms an app reacts to. */
export type ErrorKind =
  /** A UserError/ValidationError: a business rule said no. Show its message. */
  | "user"
  /** The signed-in user's groups don't allow the call: a setup problem. */
  | "access"
  /** The record is gone (MissingError). */
  | "missing"
  /** Signed out, or the session expired. */
  | "session"
  /** No answer: offline, timed out, or aborted. */
  | "network"
  /** Anything else: a bug, on one side or the other. */
  | "server";

const KIND_BY_EXCEPTION: Readonly<Record<string, ErrorKind>> = {
  "odoo.exceptions.UserError": "user",
  "odoo.exceptions.ValidationError": "user",
  "odoo.exceptions.RedirectWarning": "user",
  "odoo.exceptions.AccessError": "access",
  "odoo.exceptions.AccessDenied": "access",
  "odoo.exceptions.MissingError": "missing",
  "odoo.http.SessionExpiredException": "session",
};

/** A failed facade call. */
export class RpcError extends Error {
  override readonly name = "RpcError";

  constructor(
    message: string,
    readonly kind: ErrorKind,
    /** The Python exception, e.g. `odoo.exceptions.UserError`, when Odoo said. */
    readonly exceptionName: string | null = null,
    readonly status: number | null = null,
    options?: ErrorOptions
  ) {
    super(message, options);
  }

  /** A message written for the person using the app, worth showing as is. */
  get isUserFacing(): boolean {
    return this.kind === "user" || this.kind === "access" || this.kind === "missing";
  }

  static fromException(name: string, message: string, status: number | null): RpcError {
    return new RpcError(message, KIND_BY_EXCEPTION[name] ?? "server", name, status);
  }
}

/** How a call reaches Odoo. */
export interface Transport {
  call(
    model: string,
    method: string,
    params: object,
    signal: AbortSignal
  ): Promise<unknown>;
}

interface JsonRpcResponse {
  result?: unknown;
  error?: {message: string; data?: {name?: string; message?: string}};
}

/** 17.0 and 18.0: `/web/dataset/call_kw/<model>/<method>`, JSON-RPC 2.0. */
export class JsonRpcTransport implements Transport {
  #nextId = 0;

  constructor(private readonly origin = "") {}

  async call(
    model: string,
    method: string,
    params: object,
    signal: AbortSignal
  ): Promise<unknown> {
    const response = await post(
      `${this.origin}/web/dataset/call_kw/${model}/${method}`,
      {
        jsonrpc: "2.0",
        method: "call",
        id: ++this.#nextId,
        params: {model, method, args: [], kwargs: params},
      },
      {},
      signal
    );
    if (!response.ok) {
      throw new RpcError(
        `${response.status} ${response.statusText}`,
        httpKind(response.status),
        null,
        response.status
      );
    }
    const payload = (await response.json()) as JsonRpcResponse;
    if (payload.error) {
      const {name = "", message = payload.error.message} = payload.error.data ?? {};
      throw RpcError.fromException(name, message, response.status);
    }
    return payload.result;
  }
}

interface Json2Error {
  name?: string;
  message?: string;
}

/**
 * 19.0+: `/json/2/<model>/<method>`, the keyword arguments as the body.
 *
 * Without an API key the request carries only the session cookie, which the
 * endpoint's bearer auth accepts in place of a key for a signed-in browser.
 * With one (a kiosk, a script), it goes as `Authorization: bearer <key>`.
 */
export class Json2Transport implements Transport {
  constructor(
    private readonly options: {origin?: string; apiKey?: string; database?: string} = {}
  ) {}

  async call(
    model: string,
    method: string,
    params: object,
    signal: AbortSignal
  ): Promise<unknown> {
    const headers: Record<string, string> = {};
    if (this.options.apiKey) {
      headers["Authorization"] = `bearer ${this.options.apiKey}`;
    }
    if (this.options.database) {
      headers["X-Odoo-Database"] = this.options.database;
    }
    const response = await post(
      `${this.options.origin ?? ""}/json/2/${model}/${method}`,
      params,
      headers,
      signal
    );
    if (response.ok) {
      return response.json();
    }
    const error = (await response.json().catch(() => ({}))) as Json2Error;
    if (response.status === 401) {
      throw new RpcError(
        error.message ?? "Signed out",
        "session",
        error.name ?? null,
        401
      );
    }
    if (error.name) {
      throw RpcError.fromException(
        error.name,
        error.message ?? error.name,
        response.status
      );
    }
    throw new RpcError(
      `${response.status} ${response.statusText}`,
      httpKind(response.status),
      null,
      response.status
    );
  }
}

/** The transport for a server's major version (`odoo.info.server_version_info[0]`). */
export function transportFor(serverVersion: number): Transport {
  return serverVersion >= 19 ? new Json2Transport() : new JsonRpcTransport();
}

async function post(
  url: string,
  body: unknown,
  headers: Record<string, string>,
  signal: AbortSignal
): Promise<Response> {
  try {
    return await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json", ...headers},
      body: JSON.stringify(body),
      signal,
    });
  } catch (cause) {
    // fetch only rejects when no response came back at all.
    const message = cause instanceof Error ? cause.message : String(cause);
    throw new RpcError(message, "network", null, null, {cause});
  }
}

function httpKind(status: number): ErrorKind {
  if (status === 401 || status === 403) {
    return "session";
  }
  return status === 404 ? "missing" : "server";
}

export interface ClientOptions {
  transport: Transport;
  /** Milliseconds before a call gives up with a `network` error. */
  timeout?: number;
  /** Called once per expired session, before the call rejects; e.g. go to /web/login. */
  onSessionExpired?: () => void;
}

export interface CallOptions {
  signal?: AbortSignal;
  timeout?: number;
}

export interface Client {
  /** Call a facade; the params and the result are typed from its Python signature. */
  call<M extends Model, F extends Method<M>>(
    model: M,
    method: F,
    ...params: ParamsArg<M, F>
  ): Promise<Result<M, F>>;
  /** `call` with the params as one argument, for code generic over the method (a
   * mutation hook, a query factory), where a spread of `ParamsArg` can't resolve. */
  invoke<M extends Model, F extends Method<M>>(
    model: M,
    method: F,
    params: Params<M, F>
  ): Promise<Result<M, F>>;
  /** The same client, with a signal or timeout for the calls made through it. */
  with(options: CallOptions): Client;
}

export function createClient(
  options: ClientOptions,
  callOptions: CallOptions = {}
): Client {
  const timeout = callOptions.timeout ?? options.timeout ?? 30_000;
  async function invoke<M extends Model, F extends Method<M>>(
    model: M,
    method: F,
    params: object
  ): Promise<Result<M, F>> {
    const signals = [AbortSignal.timeout(timeout)];
    if (callOptions.signal) {
      signals.push(callOptions.signal);
    }
    try {
      // The transport returns the JSON Odoo sent; the facade's return
      // annotation, validated server side, is what makes it a Result.
      return (await options.transport.call(
        model,
        method,
        params,
        AbortSignal.any(signals)
      )) as Result<M, F>;
    } catch (error) {
      if (error instanceof RpcError && error.kind === "session") {
        options.onSessionExpired?.();
      }
      throw error;
    }
  }
  return {
    call<M extends Model, F extends Method<M>>(
      model: M,
      method: F,
      ...params: ParamsArg<M, F>
    ) {
      return invoke<M, F>(model, method, params[0] ?? {});
    },
    invoke<M extends Model, F extends Method<M>>(
      model: M,
      method: F,
      params: Params<M, F>
    ) {
      return invoke<M, F>(model, method, params as object);
    },
    with(next: CallOptions): Client {
      return createClient(options, {...callOptions, ...next});
    },
  };
}

/** The message to show for a failed call. */
export function errorMessage(error: unknown): string {
  if (error instanceof RpcError) {
    if (error.isUserFacing) {
      return error.message;
    }
    if (error.kind === "network") {
      return "Can't reach the server. Check the connection and try again.";
    }
    if (error.kind === "session") {
      return "You were signed out. Sign in again.";
    }
  }
  console.error(error);
  return error instanceof Error ? error.message : String(error);
}
