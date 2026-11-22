/** Faux XMLHttpRequest : permet de piloter progression et réponses d'un envoi de fichier. */
type Responder = (xhr: FakeXHR) => void;

export class FakeXHR {
  static instances: FakeXHR[] = [];
  /** Si défini, appelé (de façon asynchrone) à chaque send() pour répondre automatiquement. */
  static responder: Responder | null = null;

  static reset() {
    FakeXHR.instances = [];
    FakeXHR.responder = null;
  }

  method = "";
  url = "";
  headers: Record<string, string> = {};
  withCredentials = false;
  status = 0;
  responseText = "";
  body: FormData | null = null;
  aborted = false;
  upload: { onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = {
    onprogress: null,
  };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;

  constructor() {
    FakeXHR.instances.push(this);
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  send(body: FormData) {
    this.body = body;
    const responder = FakeXHR.responder;
    if (responder) setTimeout(() => responder(this), 0);
  }

  abort() {
    this.aborted = true;
    this.onabort?.();
  }

  // --- côté test ---
  progress(loaded: number, total: number) {
    this.upload.onprogress?.({ lengthComputable: true, loaded, total });
  }

  respond(status: number, body: unknown) {
    this.status = status;
    this.responseText = body === undefined ? "" : JSON.stringify(body);
    this.onload?.();
  }

  fail() {
    this.onerror?.();
  }
}
