# Flipkart Theme - Online Shop

Static storefront with Python serverless API routes for Firestore data. All Firestore
access (reads and writes) happens **server-side only**, using a Firebase service
account. No Firebase config, API key, or credential of any kind is ever sent to the
browser.

## Pages

- **index.html** -> redirects to home
- **home.html** - Home with product grid, search bar, cart drawer
- **product2.html** - Advanced product UI (gallery + offers + reviews + sticky actions)
- **cart.html** - Cart list, Place Order
- **checkout.html** - Address form
- **payment.html** - Payment (PhonePe/Paytm/Scan) and place order
- **admin.html** - Admin panel (KeyAuth login + admin token for saving data)

## Architecture

```
Browser  --GET-->  /api/data    (public, edge-cached 5 min)   --> Firestore (read)
Browser  --POST--> /api/save    (requires x-admin-token)      --> Firestore (write)
Browser  --POST--> /api/visits  (public, logs a visit)        --> Firestore (write)
Browser  --GET-->  /api/visits  (requires x-admin-token)      --> Firestore (read, stats)
```

All four routes talk to Firestore using a **service account** (`api/_firestore.py`),
never the client SDK. Firestore Security Rules can therefore be fully locked down
(`allow read, write: if false;`) since the browser never touches Firestore directly.

`/api/data` is edge-cached (`Cache-Control: public, s-maxage=300,
stale-while-revalidate=60`) so repeat visitors within 5 minutes are served instantly
from Vercel's cache instead of hitting Firestore on every page load.

## Environment variables

See `.env.example`. Set these in Vercel -> Project -> Settings -> Environment Variables
(Production **and** Preview) before deploying:

- `FIREBASE_PROJECT_ID` - your Firebase project ID
- `FIREBASE_SERVICE_ACCOUNT_JSON` - the full contents of a Firebase service account
  key, as a single-line JSON string (Firebase Console -> Project Settings -> Service
  Accounts -> Generate new private key)
- `ADMIN_TOKEN` - a password you choose yourself; required as the `x-admin-token`
  header to save products/UPI/banners or view visit stats

After adding/changing env vars, you must **redeploy** - existing deployments don't
pick up new env vars automatically.

## Firestore Security Rules

Since all access goes through the server, lock the rules down completely:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

## API routes

- `GET /api/data` - returns `{ ok, data: { products, upi, banners } }`, edge-cached
- `POST /api/save` - body `{ action: "products"|"upi"|"banners", value }`, header
  `x-admin-token` required
- `POST /api/visits` - body `{ ip, ua, path }`, logs a visit (public, no token)
- `GET /api/visits` - returns `{ ok, stats }`, header `x-admin-token` required

## Run locally

```bash
npm start
```

Then open http://localhost:3000

For backend testing use Vercel local dev after adding the env vars:

```bash
npx vercel dev
```

## Structure

- `css/flipkart.css` - Flipkart theme styles
- `js/app.js` - Frontend data helper that talks to `/api/*`
- `api/_firestore.py` - shared Firestore REST + service-account auth helper
- `api/data.py` - public, cached read endpoint
- `api/save.py` - admin-token-protected write endpoint
- `api/visits.py` - visit logging (public write) + stats (admin-token read)
- Cart and address are stored in `localStorage`.

## Theme colors

- Primary blue: `#2874f0`
- Yellow accent: `#ffe500`
- Green (off/delivery): `#388e3c`
