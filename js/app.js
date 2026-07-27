const APP = {
  _initDone: false,

  async initBackend() {
    this._initDone = true;
    return true;
  },

  async _api(path, options = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), options.timeout || 8000);

    try {
      const res = await fetch(path, {
        ...options,
        signal: ctrl.signal,
        headers: {
          "Content-Type": "application/json",
          ...(options.headers || {})
        }
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.ok === false) {
        throw new Error(data.error || `API request failed (${res.status})`);
      }
      return data;
    } finally {
      clearTimeout(timer);
    }
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
      const data = await this._api(`/api/store?key=${encodeURIComponent(key)}`);
      const value = data.value ?? null;
      if (value !== null) this._cache(key, value);
      return value;
    } catch (e) {
      console.error("Backend get error:", e);
      return this._local(key);
    }
  },

  async _set(key, value) {
    this._cache(key, value);

    try {
      await this._api(`/api/store?key=${encodeURIComponent(key)}`, {
        method: "POST",
        body: JSON.stringify({ value })
      });
      return { localSaved: true, remoteSaved: true };
    } catch (e) {
      console.error("Backend save error:", e);
      return {
        localSaved: true,
        remoteSaved: false,
        reason: e && e.message ? e.message : String(e)
      };
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
    const banners = await this._get("banners");
    return Array.isArray(banners) ? banners : [];
  },

  getBanners() {
    return this._local("banners") || [];
  },

  async saveBanners(banners) {
    const list = (banners || []).filter(v => typeof v === "string" && v.trim());
    return this._set("banners", list);
  },

  async recordVisit() {
    const sessionKey = "fk_visit_logged_session";
    if (sessionStorage.getItem(sessionKey) === "1") {
      return { saved: false, reason: "already_logged_this_session" };
    }

    try {
      const data = await this._api("/api/visits", {
        method: "POST",
        body: JSON.stringify({
          ua: navigator.userAgent || "",
          path: location.pathname || "",
          ts: Date.now()
        })
      });
      sessionStorage.setItem(sessionKey, "1");
      return { saved: true, ip: data.ip || "unknown" };
    } catch (e) {
      console.error("Visit log error:", e);
      return { saved: false, reason: e && e.message ? e.message : String(e) };
    }
  },

  async getVisitStats(limitCount = 5000) {
    try {
      const data = await this._api(`/api/visits?limit=${encodeURIComponent(limitCount)}`);
      return data.stats || { total: 0, uniqueIps: 0, repeatVisits: 0, topIps: [] };
    } catch (e) {
      console.error("Visit stats error:", e);
      return { total: 0, uniqueIps: 0, repeatVisits: 0, topIps: [] };
    }
  },

  getProductById(id) {
    return this.getProducts().find(p => p.id === id) || null;
  },

  async getProductByIdAsync(id) {
    const products = await this.getProductsAsync();
    return products.find(p => p.id === id) || null;
  },

  getOffPercent(price, mrp) {
    return mrp > price ? Math.round(((mrp - price) / mrp) * 100) : 0;
  },

  generateId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2);
  }
};
