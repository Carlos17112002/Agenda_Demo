export type QueryParams = Record<string, string | number | boolean | null | undefined>;

export type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  formData?: FormData;
  query?: QueryParams;
  auth?: boolean;
  retry?: boolean;
  accept?: string;
};

type ApiClientConfig = {
  baseUrl?: string;
  getAccessToken: () => string | null;
  getTenantContextId: () => string | null;
  fetchImpl?: typeof fetch;
};

export class ApiError extends Error {
  readonly status: number;
  readonly fields?: Record<string, string[]>;
  readonly requestId?: string;

  constructor(status: number, message: string, fields?: Record<string, string[]>, requestId?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fields = fields;
    this.requestId = requestId;
  }
}

function normalizeError(status: number, payload: unknown): ApiError {
  let message = 'Ocurrió un error inesperado.';
  let fields: Record<string, string[]> | undefined;
  let requestId: string | undefined;

  if (payload && typeof payload === 'object') {
    const data = payload as Record<string, unknown>;
    if (typeof data.detail === 'string') {
      message = data.detail;
    }
    Object.entries(data).forEach(([key, value]) => {
      if (key === 'detail') return;
      const messages = Array.isArray(value)
        ? value.filter((item): item is string => typeof item === 'string')
        : typeof value === 'string'
          ? [value]
          : [];
      if (messages.length > 0) {
        fields = { ...fields, [key]: messages };
        if (message === 'Ocurrió un error inesperado.') message = messages[0];
      }
    });
    if (typeof data.request_id === 'string') requestId = data.request_id;
  }

  if (status === 401 && message === 'Ocurrió un error inesperado.') message = 'Sesión expirada.';
  if (status === 403 && message === 'Ocurrió un error inesperado.') message = 'No tienes permiso para esta acción.';
  if (status === 0) message = 'Sin conexión con el servidor.';

  return new ApiError(status, message, fields, requestId);
}

function filenameFromDisposition(header: string | null): string | null {
  if (!header) return null;
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1].trim());
    } catch {
      return encoded[1].trim();
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : null;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly getAccessToken: () => string | null;
  private readonly getTenantContextId: () => string | null;
  private readonly fetchImpl: typeof fetch;
  private refreshHandler?: () => Promise<string>;
  private unauthorizedHandler?: () => void;
  private refreshPromise?: Promise<string>;

  constructor(config: ApiClientConfig) {
    this.baseUrl = (config.baseUrl ?? '').replace(/\/+$/, '');
    this.getAccessToken = config.getAccessToken;
    this.getTenantContextId = config.getTenantContextId;
    // El fetch nativo exige window/globalThis como receptor; sin bind, el
    // navegador lanza "Illegal invocation" al invocarlo como método.
    this.fetchImpl = config.fetchImpl ?? fetch.bind(globalThis);
  }

  configureRefresh(handler: () => Promise<string>) {
    this.refreshHandler = handler;
  }

  configureUnauthorized(handler: () => void) {
    this.unauthorizedHandler = handler;
  }

  get<T>(path: string, query?: QueryParams): Promise<T> {
    return this.request<T>(path, { query });
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, { method: 'POST', body });
  }

  postForm<T>(path: string, formData: FormData): Promise<T> {
    return this.request<T>(path, { method: 'POST', formData });
  }

  patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, { method: 'PATCH', body });
  }

  delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' });
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await this.send(path, options);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  async download(
    path: string,
    query?: QueryParams,
  ): Promise<{ blob: Blob; filename: string | null }> {
    const response = await this.send(path, { query, accept: '*/*' });
    return {
      blob: await response.blob(),
      filename: filenameFromDisposition(response.headers.get('Content-Disposition')),
    };
  }

  private async send(path: string, options: RequestOptions = {}): Promise<Response> {
    const {
      method = 'GET',
      body,
      formData,
      query,
      auth = true,
      retry = true,
      accept = 'application/json',
    } = options;
    const origin = this.baseUrl || window.location.origin;
    const url = new URL(`${origin}${path}`);
    Object.entries(query ?? {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    });

    const headers: Record<string, string> = { Accept: accept };
    if (body !== undefined && !formData) headers['Content-Type'] = 'application/json';
    if (auth) {
      const access = this.getAccessToken();
      if (access) headers.Authorization = `Bearer ${access}`;
      const contextId = this.getTenantContextId();
      if (contextId) headers['X-Tenant-Context'] = contextId;
    }

    let response: Response;
    try {
      response = await this.fetchImpl(url.toString(), {
        method,
        headers,
        body: formData ?? (body === undefined ? undefined : JSON.stringify(body)),
      });
    } catch {
      throw normalizeError(0, null);
    }

    if (response.status === 401 && auth && retry) {
      try {
        await this.refreshOnce();
      } catch {
        this.unauthorizedHandler?.();
        throw new ApiError(401, 'Sesión expirada.');
      }
      return this.send(path, { ...options, retry: false });
    }

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw normalizeError(response.status, payload);
    }

    return response;
  }

  private refreshOnce(): Promise<string> {
    if (!this.refreshPromise) {
      const promise = (async () => {
        if (!this.refreshHandler) throw new ApiError(401, 'Sesión expirada.');
        return this.refreshHandler();
      })();
      this.refreshPromise = promise.finally(() => {
        this.refreshPromise = undefined;
      });
    }
    return this.refreshPromise;
  }
}
