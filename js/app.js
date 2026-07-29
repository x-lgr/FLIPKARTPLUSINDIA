const APP = {
  _dataPromise: null,

  // Kept as a no-op for backward compatibility with admin.html calls.
  async initBackend() {
    return null;
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

  async _fetchCachedData() {
    if (this._dataPromise) return this._dataPromise;
    this._dataPromise = (async () => {
      try {
        const res = await fetch("/api/data");
        const json = await res.json().catch(() => null);
        if (json && json.ok && json.data) {
          this._cache("products", json.data.products || []);
          this._cache("upi", json.data.upi || {});
          this._cache("banners", json.data.banners || []);
          return json.data;
        }
      } catch (e) {
        console.error("Cached data fetch error:", e);
      }
      return null;
    })();
    return this._dataPromise;
  },

  _getAdminToken() {
    let token = sessionStorage.getItem("fk_admin_token");
    if (!token) {
      token = window.prompt("Enter admin token:") || "";
      if (token) sessionStorage.setItem("fk_admin_token", token);
    }
    return token;
  },

  async _adminPost(action, value) {
    const token = this._getAdminToken();
    try {
      const res = await fetch("/api/save", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-admin-token": token },
        body: JSON.stringify({ action, value })
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        sessionStorage.removeItem("fk_admin_token");
        return { localSaved: true, remoteSaved: false, reason: "Invalid admin token" };
      }
      return { localSaved: true, remoteSaved: !!(data && data.ok) };
    } catch (e) {
      return { localSaved: true, remoteSaved: false, reason: e && e.message ? e.message : String(e) };
    }
  },

  async getProductsAsync() {
    const data = await this._fetchCachedData();
    if (data) return Array.isArray(data.products) ? data.products : [];
    return this._local("products") || [];
  },

  getProducts() {
    return this._local("products") || [];
  },

  async saveProducts(products) {
    const list = products || [];
    this._cache("products", list);
    return this._adminPost("products", list);
  },

  async getUpiAsync() {
    const data = await this._fetchCachedData();
    if (data) return data.upi || { upiId: "", name: "Store", note: "Order Payment" };
    return this._local("upi") || { upiId: "", name: "Store", note: "Order Payment" };
  },

  getUpi() {
    return this._local("upi") || { upiId: "", name: "Store", note: "Order Payment" };
  },

  async saveUpi(config) {
    const value = config || {};
    this._cache("upi", value);
    return this._adminPost("upi", value);
  },

  async getBannersAsync() {
    const data = await this._fetchCachedData();
    if (data && Array.isArray(data.banners)) return data.banners;
    return this._local("banners") || [];
  },

  getBanners() {
    return this._local("banners") || [];
  },

  async saveBanners(banners) {
    const list = (banners || []).filter(value => typeof value === "string" && value.trim());
    this._cache("banners", list);
    const res = await this._adminPost("banners", list);
    return { ...res, count: list.length };
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
      const ip = await this._fetchPublicIp();
      await fetch("/api/visits", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ip, ua: navigator.userAgent || "", path: location.pathname || "" })
      });
      sessionStorage.setItem(sessionKey, "1");
      return { saved: true, ip };
    } catch (e) {
      return { saved: false, reason: e && e.message ? e.message : String(e) };
    }
  },

  async getVisitStats() {
    try {
      const token = this._getAdminToken();
      const res = await fetch("/api/visits", { headers: { "x-admin-token": token } });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) sessionStorage.removeItem("fk_admin_token");
      if (data && data.ok && data.stats) return data.stats;
    } catch (e) {
      console.error("Visit stats error:", e);
    }
    return { total: 0, uniqueIps: 0, repeatVisits: 0, topIps: [] };
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
