/* @lumina/workshop-sdk 1.0.2 —— 由 tools/bundle_sdk.mjs 内联，请勿手改（改 package.json 后重跑 pnpm bundle） */
(function () {
"use strict";
const WORKSHOP_API_VERSION = "1.0.0";
const WORKSHOP_MANIFEST_VERSION = 1;
const WORKSHOP_RPC_VERSION = 1;
const WORKSHOP_RPC_EVENT_NAMES = ["ui.stateChanged"];
const WORKSHOP_PERMISSION_NAMES = [
    "image.pick",
    "project.storage",
    "color-library.read",
    "handoff.image",
];
function createRequestEnvelope(requestId, method, payload) {
    return {
        protocol: "lumina-workshop-rpc",
        version: WORKSHOP_RPC_VERSION,
        kind: "request",
        requestId,
        method,
        payload,
    };
}
// <<< contracts.js

function applyWorkshopUiState(state, root = document.documentElement) {
    root.lang = state.locale;
    root.dataset.theme = state.theme;
    for (const [name, value] of Object.entries(state.tokens)) {
        if (/^--lumina-[a-z0-9-]+$/.test(name)) {
            root.style.setProperty(name, value);
        }
    }
}
// <<< theme.js

const DEFAULT_HANDSHAKE_TIMEOUT_MS = 10_000;
const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;
const IMAGE_PICK_REQUEST_TIMEOUT_MS = 300_000;
const HANDOFF_REQUEST_TIMEOUT_MS = 120_000;
const MAX_LOCALLY_TIMED_OUT_REQUEST_IDS = 256;
class WorkshopClientError extends Error {
    code;
    retryable;
    constructor(code, message, retryable = false) {
        super(message);
        this.name = "WorkshopClientError";
        this.code = code;
        this.retryable = retryable;
    }
}
function isRecord(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
function parseResponse(value) {
    if (!isRecord(value)) {
        return null;
    }
    if (value.protocol !== "lumina-workshop-rpc" ||
        value.version !== WORKSHOP_RPC_VERSION ||
        value.kind !== "response" ||
        typeof value.requestId !== "string" ||
        value.requestId.length === 0 ||
        typeof value.ok !== "boolean") {
        return null;
    }
    if (value.ok) {
        return value;
    }
    if (!isRecord(value.error) ||
        typeof value.error.code !== "string" ||
        typeof value.error.message !== "string" ||
        typeof value.error.retryable !== "boolean") {
        return null;
    }
    return value;
}
function parseUiState(value) {
    if (!isRecord(value) ||
        (value.locale !== "zh-CN" && value.locale !== "en-US") ||
        (value.theme !== "light" && value.theme !== "dark") ||
        !isRecord(value.tokens) ||
        Object.values(value.tokens).some((token) => typeof token !== "string")) {
        return null;
    }
    return value;
}
function parseEvent(value) {
    if (!isRecord(value) ||
        value.protocol !== "lumina-workshop-rpc" ||
        value.version !== WORKSHOP_RPC_VERSION ||
        value.kind !== "event" ||
        value.event !== "ui.stateChanged") {
        return null;
    }
    const state = parseUiState(value.payload);
    if (state === null) {
        return null;
    }
    return { ...value, payload: state };
}
class PortWorkshopClient {
    sessionId;
    image;
    projects;
    colorLibrary;
    handoff;
    ui;
    status;
    lifecycle;
    port;
    pending = new Map();
    locallyTimedOutRequestIds = new Set();
    uiStateListeners = new Set();
    latestUiState = null;
    uiStateEventSequence = 0;
    requestSequence = 0;
    closed = false;
    constructor(sessionId, port) {
        this.sessionId = sessionId;
        this.port = port;
        this.port.onmessage = (event) => this.handleMessage(event.data);
        this.port.onmessageerror = () => {
            this.failProtocol(new WorkshopClientError("MALFORMED_RESPONSE", "The Workshop host sent an unreadable response."));
        };
        this.port.start();
        this.image = {
            pick: () => this.request("image.pick", {}, [], IMAGE_PICK_REQUEST_TIMEOUT_MS),
        };
        this.projects = {
            save: (record) => this.request("project.save", { record }),
            load: (projectId) => this.request("project.load", {
                projectId,
            }),
            latest: () => this.request("project.latest", {}),
            remove: (projectId) => this.request("project.remove", { projectId }),
        };
        this.colorLibrary = {
            read: () => this.request("colorLibrary.read", {}),
        };
        this.handoff = {
            image: (value) => this.request("handoff.image", value, value.svgBytes instanceof ArrayBuffer &&
                value.svgBytes !== value.pngBytes
                ? [value.pngBytes, value.svgBytes]
                : [value.pngBytes], HANDOFF_REQUEST_TIMEOUT_MS),
        };
        this.ui = {
            getState: async () => {
                if (this.closed) {
                    throw new WorkshopClientError("CLIENT_CLOSED", "The Workshop connection has been closed.");
                }
                if (this.latestUiState !== null) {
                    return this.latestUiState;
                }
                const eventSequenceAtRequest = this.uiStateEventSequence;
                const state = await this.request("ui.getState", {});
                if (this.uiStateEventSequence !== eventSequenceAtRequest &&
                    this.latestUiState !== null) {
                    return this.latestUiState;
                }
                return state;
            },
            subscribeState: (listener) => {
                if (this.closed) {
                    return () => { };
                }
                this.uiStateListeners.add(listener);
                if (this.latestUiState !== null) {
                    this.notifyUiStateListener(listener, this.latestUiState);
                }
                return () => {
                    this.uiStateListeners.delete(listener);
                };
            },
        };
        this.status = {
            progress: (value) => this.request("status.progress", value),
            error: (value) => this.request("status.error", value),
            diagnostics: (value) => this.request("status.diagnostics", value),
        };
        this.lifecycle = {
            ready: () => this.request("lifecycle.ready", {}),
        };
    }
    close() {
        if (this.closed) {
            return;
        }
        this.closed = true;
        this.port.onmessage = null;
        this.port.onmessageerror = null;
        this.port.close();
        this.uiStateListeners.clear();
        this.rejectAll(new WorkshopClientError("CLIENT_CLOSED", "The Workshop connection has been closed."));
    }
    request(method, payload, transfer = [], timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS) {
        if (this.closed) {
            return Promise.reject(new WorkshopClientError("CLIENT_CLOSED", "The Workshop connection has been closed."));
        }
        this.requestSequence += 1;
        const requestId = `req-${this.requestSequence}`;
        const envelope = createRequestEnvelope(requestId, method, payload);
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                this.pending.delete(requestId);
                this.rememberTimedOutRequestId(requestId);
                reject(new WorkshopClientError("REQUEST_TIMEOUT", `Workshop request ${method} timed out.`, true));
            }, timeoutMs);
            this.pending.set(requestId, {
                resolve: (value) => resolve(value),
                reject,
                timeout,
            });
            try {
                this.port.postMessage(envelope, transfer);
            }
            catch (error) {
                clearTimeout(timeout);
                this.pending.delete(requestId);
                reject(new WorkshopClientError("REQUEST_SEND_FAILED", error instanceof Error
                    ? error.message
                    : `Workshop request ${method} could not be sent.`, true));
            }
        });
    }
    handleMessage(value) {
        const event = parseEvent(value);
        if (event !== null) {
            this.publishUiState(event.payload);
            return;
        }
        if (isRecord(value) && value.kind === "event") {
            return;
        }
        const response = parseResponse(value);
        if (response === null) {
            this.failProtocol(new WorkshopClientError("MALFORMED_RESPONSE", "The Workshop host sent a malformed response."));
            return;
        }
        const pending = this.pending.get(response.requestId);
        if (pending === undefined) {
            if (this.locallyTimedOutRequestIds.delete(response.requestId)) {
                return;
            }
            this.failProtocol(new WorkshopClientError("DUPLICATE_RESPONSE", "The Workshop host sent a duplicate or unknown response."));
            return;
        }
        clearTimeout(pending.timeout);
        this.pending.delete(response.requestId);
        if (response.ok) {
            pending.resolve(response.result);
            return;
        }
        const error = response.error;
        pending.reject(new WorkshopClientError(error?.code ?? "HOST_REQUEST_FAILED", error?.message ?? "The Workshop host rejected the request.", error?.retryable ?? false));
    }
    publishUiState(state) {
        this.latestUiState = state;
        this.uiStateEventSequence += 1;
        for (const listener of [...this.uiStateListeners]) {
            this.notifyUiStateListener(listener, state);
        }
    }
    notifyUiStateListener(listener, state) {
        try {
            listener(state);
        }
        catch {
            // A module listener must not interrupt other listeners or the RPC link.
        }
    }
    failProtocol(error) {
        if (this.closed) {
            return;
        }
        this.closed = true;
        this.port.onmessage = null;
        this.port.onmessageerror = null;
        this.port.close();
        this.uiStateListeners.clear();
        this.latestUiState = null;
        this.rejectAll(error);
    }
    rejectAll(error) {
        for (const pending of this.pending.values()) {
            clearTimeout(pending.timeout);
            pending.reject(error);
        }
        this.pending.clear();
        this.locallyTimedOutRequestIds.clear();
    }
    rememberTimedOutRequestId(requestId) {
        this.locallyTimedOutRequestIds.add(requestId);
        if (this.locallyTimedOutRequestIds.size <=
            MAX_LOCALLY_TIMED_OUT_REQUEST_IDS) {
            return;
        }
        const oldestRequestId = this.locallyTimedOutRequestIds
            .values()
            .next().value;
        if (oldestRequestId !== undefined) {
            this.locallyTimedOutRequestIds.delete(oldestRequestId);
        }
    }
}
async function connectWorkshop(options) {
    const windowObject = options.windowObject ??
        window;
    const handshakeTimeoutMs = options.handshakeTimeoutMs ?? DEFAULT_HANDSHAKE_TIMEOUT_MS;
    return new Promise((resolve, reject) => {
        let settled = false;
        const finishWithError = (error) => {
            if (settled) {
                return;
            }
            settled = true;
            clearTimeout(timeout);
            windowObject.removeEventListener("message", onMessage);
            reject(error);
        };
        const onMessage = (event) => {
            if (event.source !== windowObject.parent) {
                return;
            }
            if (!isRecord(event.data) || event.data.type !== "lumina.workshop.connect") {
                return;
            }
            if (typeof event.data.sessionId !== "string" ||
                event.data.sessionId.length === 0 ||
                event.ports.length !== 1) {
                finishWithError(new WorkshopClientError("HANDSHAKE_INVALID", "The Workshop host supplied an invalid connection."));
                return;
            }
            settled = true;
            clearTimeout(timeout);
            windowObject.removeEventListener("message", onMessage);
            resolve(new PortWorkshopClient(event.data.sessionId, event.ports[0]));
        };
        const timeout = setTimeout(() => {
            finishWithError(new WorkshopClientError("HANDSHAKE_TIMEOUT", "The Workshop host did not connect within 10 seconds.", true));
        }, handshakeTimeoutMs);
        windowObject.addEventListener("message", onMessage);
        try {
            const readyMessage = {
                type: "lumina.workshop.ready",
                moduleId: options.moduleId,
                moduleVersion: options.moduleVersion,
                apiVersion: WORKSHOP_API_VERSION,
                events: [...WORKSHOP_RPC_EVENT_NAMES],
            };
            windowObject.parent.postMessage(readyMessage, "*");
        }
        catch (error) {
            finishWithError(new WorkshopClientError("HANDSHAKE_SEND_FAILED", error instanceof Error
                ? error.message
                : "The Workshop ready message could not be sent.", true));
        }
    });
}
// <<< client.js

  window.LuminaWorkshop = { connectWorkshop, WorkshopClientError, WORKSHOP_API_VERSION, WORKSHOP_MANIFEST_VERSION, WORKSHOP_RPC_VERSION, WORKSHOP_PERMISSION_NAMES, applyWorkshopUiState, createRequestEnvelope };
})();
