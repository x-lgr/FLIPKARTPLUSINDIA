const APP = {
  _db: null,
  _initPromise: null,

  async initBackend() {
    if (this._db) return this._db;
    if (this._initPromise) return this._initPromise;

    this._initPromise = (async () => {
      await this._loadFirebaseSdk();
      const config = await this._loadFirebaseConfig();

      if (!window.firebase.apps.length) {
        window.firebase.initializeApp(config);
      }

      this._db = window.firebase.firestore();
      this._db.enablePersistence({ synchronizeTabs: true }).catch(() => {});
      return this._db;
    })();

    return this._initPromise;
  },

  async _loadFirebaseConfig() {
    const res = await fetch("/api/firebase-config", { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.config || !data.config.apiKey || !data.config.projectId) {
      throw new Error("Firebase config missing from backend env.");
    }
    return data.config;
  },

  _loadScript(src) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`script[src="${src}"]`)) {
        resolve();
        return;
      }
      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`Failed to load ${src}`));
      document.head.appendChild(script);
    });
  },

  async _loadFirebaseSdk() {
    if (window.firebase && window.firebase.firestore) return;
    await this._loadScript("https://www.gstatic.com/firebasejs/9.22.1/firebase-app-compat.js");
    await this._loadScript("https://www.gstatic.com/firebasejs/9.22.1/firebase-firestore-compat.js");
  },

  _local(key) {
    try {
      const value = localStorage.getItem("fk_" + key);
      return value ? JSON.parse(value) : null;
    } catch {
      return null;
    }
  },

  _cache(key, value) {
    localStorage.setItem("fk_" + key, JSON.stringify(value));
  },

  async _get(key) {
    try {
      const db = await this.initBackend();
      const doc = await db.collection("store").doc(key).get();
      if (doc.exists) {
        const value = doc.data().value;
        this._cache(key, value);
        return value;
      }
    } catch (e) {
      console.error("Firebase get error:", e);
    }
    return this._local(key);
  },

  async _set(key, value) {
    this._cache(key, value);
    try {
      const db = await this.initBackend();
      await db.collection("store").doc(key).set({ value, updatedAt: Date.now() });
      return { localSaved: true, remoteSaved: true };
    } catch (e) {
      console.error("Firebase save error:", e);
      return { localSaved: true, remoteSaved: false, reason: e && e.message ? e.message : String(e) };
    }
  },

  async getProductsAsync() {
    const products = await this._get("products");
    return Array.isArray(products) ? products : [];
  },

  getProducts() {
    return this._local("products") || [];
  },

  async saveProducts(products) {
    return this._set("products", products || []);
  },

  async getUpiAsync() {
    const upi = await this._get("upi");
    return upi || { upiId: "", name: "Store", note: "Order Payment" };
  },

  getUpi() {
    return this._local("upi") || { upiId: "", name: "Store", note: "Order Payment" };
  },

  async saveUpi(config) {
    return this._set("upi", config || {});
  },

  async getBannersAsync() {
    try {
      const db = await this.initBackend();
      const snap = await db.collection("store_banners").orderBy("idx").get();
      if (!snap.empty) {
        const list = snap.docs
          .map(doc => doc.data().value)
          .filter(value => typeof value === "string" && value.trim());
        this._cache("banners", list);
        return list;
      }
    } catch (e) {
      console.error("Firebase banners get error:", e);
    }

    const banners = await this._get("banners");
    return Array.isArray(banners) ? banners : [];
  },

  getBanners() {
    return this._local("banners") || [];
  },

  async saveBanners(banners) {
    const list = (banners || []).filter(value => typeof value === "string" && value.trim());
    this._cache("banners", list);

    try {
      const db = await this.initBackend();
      const col = db.collection("store_banners");
      const old = await col.get();
      const batch = db.batch();
      old.forEach(doc => batch.delete(doc.ref));
      list.forEach((value, idx) => {
        batch.set(col.doc("b_" + String(idx).padStart(3, "0")), {
          idx,
          value,
          updatedAt: Date.now()
        });
      });
      await batch.commit();
      await db.collection("store").doc("banners").delete().catch(() => {});
      return { localSaved: true, remoteSaved: true, count: list.length };
    } catch (e) {
      console.error("Firebase banners save error:", e);
      return { localSaved: true, remoteSaved: false, reason: e && e.message ? e.message : String(e) };
    }
  },

  async _fetchPublicIp() {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 3500);
      const res = await fetch("https://api.ipify.org?format=json", { signal: ctrl.signal });
      clearTimeout(timer);
      if (!res.ok) return "unknown";
      const data = await res.json();
      return data && data.ip ? String(data.ip) : "unknown";
    } catch {
      return "unknown";
    }
  },

  async recordVisit() {
    const sessionKey = "fk_visit_logged_session";
    if (sessionStorage.getItem(sessionKey) === "1") {
      return { saved: false, reason: "already_logged_this_session" };
    }

    try {
      const db = await this.initBackend();
      const payload = {
        ip: await this._fetchPublicIp(),
        ua: navigator.userAgent || "",
        path: location.pathname || "",
        ts: Date.now()
      };
      await db.collection("store_visits").add(payload);
      sessionStorage.setItem(sessionKey, "1");
      return { saved: true, ip: payload.ip };
    } catch (e) {
      return { saved: false, reason: e && e.message ? e.message : String(e) };
    }
  },

  async getVisitStats(limitCount = 5000) {
    try {
      const db = await this.initBackend();
      const snap = await db.collection("store_visits").orderBy("ts", "desc").limit(limitCount).get();
      const ipCount = {};
      snap.forEach(doc => {
        const data = doc.data() || {};
        const ip = data.ip && String(data.ip).trim() ? String(data.ip).trim() : "unknown";
        ipCount[ip] = (ipCount[ip] || 0) + 1;
      });
      const ips = Object.keys(ipCount);
      const total = snap.size;
      const topIps = ips
        .sort((a, b) => ipCount[b] - ipCount[a])
        .slice(0, 8)
        .map(ip => ({ ip, count: ipCount[ip] }));
      return {
        total,
        uniqueIps: ips.length,
        repeatVisits: Math.max(total - ips.length, 0),
        topIps
      };
    } catch (e) {
      console.error("Visit stats error:", e);
      return { total: 0, uniqueIps: 0, repeatVisits: 0, topIps: [] };
    }
  },

  getProductById(id) {
    return this.getProducts().find(product => product.id === id) || null;
  },

  async getProductByIdAsync(id) {
    const products = await this.getProductsAsync();
    return products.find(product => product.id === id) || null;
  },

  getOffPercent(price, mrp) {
    return mrp > price ? Math.round(((mrp - price) / mrp) * 100) : 0;
  },

  generateId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2);
  }
};
