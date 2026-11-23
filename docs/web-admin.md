# Panel web del operador

SPA en `web/` para operar una empresa de AGENDA: agenda, clientes, servicios,
equipo, inventario (solo lectura), resumen y marca. Consume la misma API que la
app móvil; no hay endpoints exclusivos del panel.

## Requisitos

- Node.js 24 y npm.
- Backend en `http://127.0.0.1:8000` con migraciones aplicadas.
- Una empresa con al menos una sucursal y una cuenta con membresía en ella
  (propietario, administrador o trabajador).

## Desarrollo local

Terminal 1:

```bash
cd backend
python manage.py runserver
```

Terminal 2:

```bash
cd web
cp .env.example .env
npm install
npm run dev
```

Abre `http://127.0.0.1:5173`. Vite hace proxy de `/api` y `/media` hacia
Django; ese proxy solo existe en desarrollo. En Windows usa
`Copy-Item .env.example .env` en PowerShell.

## Variables de entorno

| Archivo | Variable | Uso |
| --- | --- | --- |
| `web/.env` | `VITE_API_BASE_URL` | API del panel. Vacío usa el mismo origen; en desarrollo el proxy de Vite reenvía `/api`. |
| `web/.env.e2e` | `E2E_WEB_URL`, `E2E_API_URL`, `E2E_EMAIL`, `E2E_PASSWORD`, `E2E_COMPANY`, `E2E_OTHER_COMPANY` | Pruebas Playwright. Copia `web/.env.e2e.example`. |
| `web/.env.production` | `VITE_API_BASE_URL` | Build de producción. Déjalo vacío para mismo origen detrás de Nginx. |

`.env`, `.env.e2e`, `.env.production` y `web/e2e/.auth/` no se versionan.

## Scripts

| Comando | Efecto |
| --- | --- |
| `npm run dev` | Vite en `5173` con proxy a Django. |
| `npm run lint` | ESLint sobre TypeScript, hooks y accesibilidad. |
| `npm run test` | Vitest + React Testing Library + MSW. |
| `npm run build` | Chequeo de tipos y build en `dist/`. |
| `npm run preview` | Sirve `dist/` sin proxy; solo para revisar el bundle. |
| `npm run e2e` | Playwright contra Django y Vite. |
| `npm run e2e:install` | Instala Chromium para Playwright. |

## Sesión y aislamiento

- El access token vive en memoria; el refresh token y
  `{companyId, contextId, companyName}` se guardan en `localStorage`. No se
  persisten datos de negocio.
- Cambiar de empresa crea un contexto tenant nuevo y limpia la caché de
  TanStack Query. Cada consulta envía `X-Tenant-Context` y cada clave de caché
  incluye la empresa.
- Un usuario puede tener hasta 20 contextos tenant activos (8 horas cada uno).
  Si el servidor rechaza uno nuevo, cierra sesiones antiguas desde las otras
  pestañas o equipos.

## Pruebas de punta a punta

```bash
cd web
cp .env.e2e.example .env.e2e
# completa E2E_PASSWORD con la clave de la cuenta de pruebas
npm run e2e:install
npm run e2e
```

Playwright levanta Vite; Django debe estar en ejecución. `globalSetup` hace un
login real y crea una sola sesión compartida; las pruebas inyectan esa sesión y
simulan la renovación para no agotar el límite de contextos. Si
`E2E_OTHER_COMPANY` no existe, la prueba de aislamiento se omite. La suite crea
clientes, servicios, horarios y reservas reales: no la ejecutes contra
producción.

## Build y despliegue

```bash
cd web
cp .env.production.example .env.production
npm ci
npm run build
```

El resultado queda en `web/dist/`. Para servir panel y API en el mismo origen,
usa `web/deploy/nginx.conf.example` como base: sirve `dist/` con fallback a
`index.html`, hace proxy de `/api/`, `/b/` y `/media/`, y aplica CSP, HSTS
opcional y caché de assets.

Antes de publicar:

- Ajusta `root`, `alias` y `server_name` a las rutas y al dominio reales.
- Agrega el dominio a `DJANGO_ALLOWED_HOSTS` y usa `DJANGO_DEBUG=false`.
- Define `DJANGO_CSRF_TRUSTED_ORIGINS=https://panel.example.com` (obligatorio en
  producción) y `DJANGO_CORS_ORIGINS` solo si panel y API quedan en orígenes
  distintos; con el proxy de Nginx no hace falta CORS. En ese caso agrega
  también la URL absoluta de la API a `connect-src` en el CSP.
- Asegura que Nginx pueda leer `backend/media/` (logos) y que el proceso de
  Django escriba ahí.
- El admin de Django vive en `DJANGO_ADMIN_PATH` (por defecto `/admin/`) y no se
  publica en el ejemplo de Nginx: expónlo solo tras VPN o lista de IPs. Necesita
  `STATIC_ROOT` y `collectstatic`, que todavía no están configurados.
- Nginx termina TLS: `SECURE_PROXY_SSL_HEADER` ya se activa con
  `DJANGO_DEBUG=false`. HSTS solo con HTTPS estable; el ejemplo lo deja
  comentado a propósito.
- `client_max_body_size` es 3 MB general y 55 MB en `/api/` para los documentos
  de inventario (límite de 50 MB por archivo).
- Postgres, servidor de aplicaciones, correo y push pertenecen al plan general
  de despliegue.

## Seguridad asumida en v1

El refresh token en `localStorage` se acepta para v1 con CSP estricta y sin
scripts de terceros. Antes de exponer el panel a internet se migrará a cookie
httpOnly con CSRF. El CSP de ejemplo permite estilos en línea porque React
aplica las variables de la marca; los scripts solo se cargan del mismo origen.

El backend registra en el logger `agenda.security` los accesos fallidos, los
tokens de recuperación inválidos y las respuestas 401/403/429, además de limitar
los intentos de login del admin de Django. La API aplica throttling por IP y
usuario, rota refresh tokens y revoca sesiones al cambiar la clave o desactivar
la cuenta.

## Validación manual

- Claro y oscuro en agenda, clientes, servicios, equipo, inventario, resumen y
  marca, a 1280 px y 768 px, sin desbordes horizontales del documento.
- Navegación completa por teclado, foco visible y diálogos con foco atrapado.
- Login, cambio de empresa y recarga: se restaura la sesión y no aparecen datos
  de la empresa anterior.
- Una cuenta sin `company.manage` no puede editar la marca; sin escritura en un
  módulo no ve sus acciones de alta o edición.

## Problemas frecuentes

- **401**: el access token expiró y el refresh falló; vuelve a iniciar sesión.
  El login acepta 5 intentos por minuto e IP.
- **403**: falta permiso, contexto tenant o la cuenta no pertenece a la empresa.
- **402**: límite del plan alcanzado (por ejemplo, trabajadores o sucursales).
- **Sin conexión**: la API no responde o `VITE_API_BASE_URL` apunta a otro
  origen sin CORS.
- **Sin sucursales o servicios**: completa la configuración de la empresa antes
  de usar la agenda.
