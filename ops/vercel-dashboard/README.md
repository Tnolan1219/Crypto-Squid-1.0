# Vercel Remote Dashboard (Proxy)

This folder is a minimal Vercel project that proxies secure calls to your VPS API.

## Env vars (set in Vercel project)
- `TRADER_API_BASE_URL` = `https://bot-api.yourdomain.com`
- `TRADER_API_TOKEN` = same value as VPS `.env` -> `CONTROL_API_TOKEN`

## Deploy
1. Install CLI locally once: `npm i -g vercel`
2. From this folder run: `vercel --prod`

## Endpoints provided by this Vercel app
- `/api/health`
- `/api/snapshot`
- `/api/control?action=start|stop|status`

## Notes
- Token stays server-side in Vercel env vars.
- Browser never sees your VPS control token.
