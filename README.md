# Flipkart Theme - Online Shop

Static storefront with Python serverless API routes for Firebase/Firestore data. Firebase config is read from Vercel environment variables, so it is not exposed in frontend JavaScript source.

## Pages

- **index.html** → redirects to home
- **home.html** – Home with product grid, search bar, cart drawer
- **product2.html** – Advanced product UI (gallery + offers + reviews + sticky actions)
- **cart.html** – Cart list, Place Order
- **checkout.html** – Address form
- **payment.html** – Payment (COD/UPI) and place order

## Backend

Set these Vercel environment variables before deploying:

```bash
FIREBASE_DATABASE_URL=https://your-project-default-rtdb.firebaseio.com
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_API_KEY=your-web-api-key
FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
FIREBASE_MESSAGING_SENDER_ID=sender-id
FIREBASE_APP_ID=app-id
FIREBASE_MEASUREMENT_ID=measurement-id
```

The frontend loads Firebase config from `/api/firebase-config`, so the config is not hardcoded in `js/app.js`. Data sync uses the Firebase Web SDK, matching the original working flow.

API routes:

- `/api/store?key=products`
- `/api/store?key=upi`
- `/api/store?key=banners`
- `/api/visits`

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

- `css/flipkart.css` – Flipkart theme styles
- `js/app.js` – Frontend data helper that talks to `/api`
- `api/` – Python serverless backend for Firestore
- Cart and address are stored in `localStorage`.

## Theme colors

- Primary blue: `#2874f0`
- Yellow accent: `#ffe500`
- Green (off/delivery): `#388e3c`
