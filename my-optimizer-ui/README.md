# ETF Optimizer React Client

This directory contains the React 19/Vite user interface for the ETF Portfolio Optimization Platform. It communicates with the FastAPI service in `../backend` and optionally uses Supabase for authentication.

For complete setup, architecture, API, data, and troubleshooting documentation, see the repository's [main README](../../README.md).

## Local development

```powershell
npm install
npm run dev
```

Vite normally serves the application at `http://localhost:5173`.

Create `.env.local` when non-default values are needed:

```dotenv
VITE_API_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=https://<project-id>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<supabase-publishable-key>
```

Do not put database passwords, Supabase service-role keys, or other server secrets in Vite environment variables. Values prefixed with `VITE_` are included in browser-accessible code.

## Commands

| Command | Purpose |
|---|---|
| `npm run dev` | Start the development server with hot reload. |
| `npm run build` | Create a production bundle in `dist/`. |
| `npm run lint` | Run ESLint over the client source. |
| `npm run preview` | Serve the production bundle locally for verification. |
