/* Mini-app KFC — Telegram WebApp multi-user. */

const tg = window.Telegram ? window.Telegram.WebApp : null;
if (tg) {
  tg.ready();
  tg.expand();
}

const api = async (path, body, method) => {
  const opt = {
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": (tg && tg.initData) ? tg.initData : "",
    },
  };
  if (method) {
    opt.method = method;
    if (body !== undefined) opt.body = JSON.stringify(body);
  } else if (body !== undefined) {
    opt.method = "POST";
    opt.body = JSON.stringify(body);
  }
  const r = await fetch(path, opt);
  let data = {};
  try { data = await r.json(); } catch (e) {}
  if (!r.ok) {
    const err = new Error(data.error || `Erreur ${r.status}`);
    err.code = data.code || null;
    err.status = r.status;
    err.payload = data;
    if (data.code === "SHOP_INACTIVE") {
      showShopInactive(data.error, data.prochaineHeure);
    }
    throw err;
  }
  return data;
};

const $ = (id) => document.getElementById(id);

const state = {
  menuLoaded: false,
  categories: [],
  currentItem: null,   // { name, modgrps }
  cartCount: 0,
  points: 0,
  pointsLimit: 2500,
  lastOrder: null,     // { number, uuid, state }
  walletMoyens: [],
  topupDemandeId: null,
  topupMontant: null,
  topupDemande: null,
  showAdmin: false,
  hasMaCommande: false,
  adminOrderId: null,
  adminPaiementId: null,
  gestionResource: null,
  gestionMeta: null,
  _preuveObjectUrls: [],
};

const POINTS_LIMIT_MSG =
  "Vous avez atteint le max d'ajout au panier pour certains articles. " +
  "Soumettez celui-ci avant de pouvoir commander à nouveau ces articles. " +
  "Vous pouvez faire plusieurs commandes successives sans souci. " +
  "Vous pouvez également supprimer des articles de votre panier actuel.";

function updatePointsLimitBanner() {
  const banner = $("points-limit-banner");
  if (!banner) return;
  const cats = state.categories || [];
  // Affichage seul : canAdd vient du backend (select-store / recalcul serveur).
  const anyBlocked = cats.some((cat) =>
    (cat.items || []).some(
      (it) => it.available !== false && it.price != null && it.canAdd === false
    )
  );
  banner.hidden = !anyBlocked;
  if (anyBlocked) banner.textContent = POINTS_LIMIT_MSG;
}

function showPointsLimitOverlay() {
  const ov = $("points-limit-overlay");
  const txt = $("points-limit-overlay-text");
  if (txt) txt.textContent = POINTS_LIMIT_MSG;
  if (ov) ov.hidden = false;
}

function closePointsLimitOverlay() {
  const ov = $("points-limit-overlay");
  if (ov) ov.hidden = true;
}

function refreshMenuLimits() {
  if (!state.menuLoaded || !state.categories.length) {
    updatePointsLimitBanner();
    return;
  }
  renderMenu(state.categories);
}

/* ---------- Navigation entre écrans ---------- */
function showScreen(name) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  const el = $("screen-" + name);
  if (el) el.classList.add("active");
}

function setNav(nav) {
  document.querySelectorAll(".nav-item").forEach((n) =>
    n.classList.toggle("active", n.dataset.nav === nav)
  );
}

/* ---------- Toast ---------- */
let toastTimer = null;
function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 2600);
}

/* ---------- Recherche de resto ---------- */
async function doSearch() {
  const q = $("search-input").value.trim();
  if (!q) return;
  const btn = $("search-btn");
  $("search-results").innerHTML = "";
  $("search-empty").hidden = true;
  btn.disabled = true;
  btn.textContent = "…";
  try {
    const { stores } = await api("/api/search", { query: q });
    if (!stores.length) {
      $("search-empty").hidden = false;
      return;
    }
    stores.forEach((s) => {
      const div = document.createElement("div");
      const available = s.available !== false;
      div.className = "store-item" + (available ? "" : " unavailable");
      const badge = available
        ? ""
        : `<div class="s-badge">${escapeHtml(s.unavailableLabel || "KFC indisponible")}</div>`;
      div.innerHTML = `
        <div class="s-main">
          <div class="s-name">${escapeHtml(s.name)}</div>
          <div class="s-city">${escapeHtml(s.city)}</div>
        </div>
        ${badge}`;
      if (available) {
        div.onclick = () => selectStore(s);
      } else {
        div.setAttribute("aria-disabled", "true");
        div.title = "KFC indisponible";
      }
      $("search-results").appendChild(div);
    });
  } catch (e) {
    toast(networkMessage(e));
  } finally {
    btn.disabled = false;
    btn.textContent = "Rechercher";
  }
}

/* Message clair si le backend n'est pas joignable ("Failed to fetch"). */
function networkMessage(e) {
  const msg = (e && e.message) || "";
  if (/fetch/i.test(msg)) {
    return "Serveur injoignable. Lancez : python -m webapp.server";
  }
  return msg || "Erreur inattendue";
}

function showAutoshopUnavailable(message) {
  const msg =
    message ||
    "Service d'autoshop indisponible suite a une maintenance, veuillez patienter puis reessayer ulterieurement.";
  const panel = $("autoshop-lock");
  const text = $("autoshop-lock-text");
  if (text) text.textContent = msg;
  if (panel) panel.hidden = false;
  document.body.classList.add("autoshop-locked");
}

function showShopInactive(message, prochaineHeure) {
  const heure =
    (prochaineHeure && String(prochaineHeure).trim()) ||
    "aucune date fourni par l'admin";
  const msg =
    message ||
    (
      "Le shop est inactif pour le moment.\n\n" +
      "Vous devez attendre qu'il soit a nouveau actif pour commander. " +
      "La disponibilite depend des moments de la journee.\n\n" +
      "La prochaine heure d'ouverture sera :\n" +
      heure
    );
  showAutoshopUnavailable(msg);
}

function isShopInactiveError(e) {
  return !!(e && e.code === "SHOP_INACTIVE");
}

function isAutoshopUnavailableError(e) {
  if (!e) return false;
  if (e.code === "AUTOSHOP_UNAVAILABLE") return true;
  if (e.code === "SHOP_INACTIVE") return true;
  const msg = String(e.message || "");
  return /autoshop indisponible|maintenance|shop est inactif/i.test(msg);
}

/* ---------- Sélection du resto -> menu ---------- */
async function selectStore(s) {
  if (s.available === false) {
    toast("KFC indisponible");
    return;
  }
  showScreen("menu");
  setNav("boutique");
  $("menu-loading").hidden = false;
  $("menu-container").innerHTML = "";
  try {
    const data = await api("/api/select-store", { storeId: s.id, name: s.name, city: s.city });
    state.menuLoaded = true;
    state.categories = data.categories;
    if (data.pointsLimit != null) state.pointsLimit = data.pointsLimit;
    if (data.points != null) state.points = data.points;
    renderMenu(data.categories);
    refreshCart();
  } catch (e) {
    if (isAutoshopUnavailableError(e)) {
      showAutoshopUnavailable(e.message);
      return;
    }
    toast(e.message);
    // Si blacklisté à la volée, revenir à la recherche pour rafraîchir le badge.
    if (/indisponible/i.test(e.message || "")) {
      backToSearch();
      doSearch();
      return;
    }
    $("menu-container").innerHTML = `<div class="empty-hint">${escapeHtml(e.message)}</div>`;
  } finally {
    $("menu-loading").hidden = true;
  }
}

function renderMenu(categories) {
  const c = $("menu-container");
  c.innerHTML = "";
  if (!categories.length) {
    c.innerHTML = `<div class="empty-hint">Aucun article fidélité disponible dans ce restaurant.</div>`;
    updatePointsLimitBanner();
    return;
  }
  updatePointsLimitBanner();
  categories.forEach((cat) => {
    const title = document.createElement("div");
    title.className = "cat-title";
    title.textContent = cat.name;
    c.appendChild(title);

    const grid = document.createElement("div");
    grid.className = "product-grid";
    cat.items.forEach((it) => {
      const card = document.createElement("div");
      const inCatalog = it.available !== false && it.price != null;
      const canAdd = inCatalog && it.canAdd !== false;
      const overLimit = inCatalog && it.canAdd === false;
      card.className = canAdd
        ? "product-card"
        : overLimit
          ? "product-card unavailable over-limit"
          : "product-card unavailable";
      const imgUrl = it.image ? `https://static.kfc.fr/images/items/xs/${encodeURIComponent(it.image)}.jpg` : "";
      const thumb = imgUrl
        ? `<img class="product-img" src="${imgUrl}" alt="${escapeHtml(it.name)}" loading="lazy"
             onerror="this.style.display='none';this.nextElementSibling.style.display='flex';" />
           <div class="product-thumb" style="display:none">
             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 8h10l-1 12H8L7 8z"/><path d="M6 8h12"/><path d="M9 8a3 3 0 0 1 6 0"/></svg>
           </div>`
        : `<div class="product-thumb">
             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 8h10l-1 12H8L7 8z"/><path d="M6 8h12"/><path d="M9 8a3 3 0 0 1 6 0"/></svg>
           </div>`;
      let priceHtml;
      if (!inCatalog) {
        priceHtml = `<div class="product-price soon">Bientôt disponible</div>`;
      } else if (overLimit) {
        priceHtml = `<div class="product-price soon">Limite panier atteinte</div>`;
      } else {
        // Prix final serveur uniquement (pas de % / prix catalogue).
        priceHtml = `<div class="product-price-row">
             <span class="price-new">${Number(it.price).toFixed(2)} €</span>
           </div>`;
      }
      card.innerHTML = `
        ${thumb}
        <div class="product-info">
          <div class="product-name">${escapeHtml(it.name)}</div>
          ${priceHtml}
        </div>`;
      if (canAdd) {
        card.onclick = () => onItemClick(it);
      } else if (overLimit) {
        card.onclick = () => showPointsLimitOverlay();
      }
      grid.appendChild(card);
    });
    c.appendChild(grid);
  });
}

/* ---------- Clic sur un article ---------- */
async function onItemClick(it) {
  if (it.available === false || it.price == null) {
    toast("Bientôt disponible");
    return;
  }
  if (it.canAdd === false) {
    showPointsLimitOverlay();
    return;
  }
  if (!it.hasOptions) {
    await addItem(it.id, []);
    return;
  }
  try {
    const data = await api("/api/item-options", { itemId: it.id });
    // Aucun vrai choix (que des groupes techniques) -> ajout direct.
    if (!data.modgrps || !data.modgrps.length) {
      await addItem(it.id, []);
      return;
    }
    state.currentItem = { id: it.id, name: data.name, modgrps: data.modgrps };
    openOptions(data.name, data.modgrps);
  } catch (e) {
    toast(e.message);
  }
}

/* ---------- Modale d'options (modgrps) — récursive ---------- */
let _grpUid = 0;

function openOptions(name, modgrps) {
  $("options-title").textContent = name;
  const body = $("options-body");
  body.innerHTML = "";
  _grpUid = 0;
  renderGroups(modgrps || [], body);
  $("options-overlay").hidden = false;
}

function renderGroups(groups, container) {
  groups.forEach((group) => {
    const wrap = document.createElement("div");
    wrap.className = "opt-group";
    wrap._group = group;

    const multi = group.max > 1;
    const min = group.min || 0;
    const hint = multi
      ? `Choisissez jusqu'à ${group.max}`
      : min >= 1
      ? "Choisissez une option"
      : "Optionnel";

    wrap.innerHTML = `
      <div class="opt-group-name">${escapeHtml(group.name)}</div>
      <div class="opt-group-hint">${hint}</div>`;

    const uid = "grp-" + _grpUid++;

    group.modifiers.forEach((mod) => {
      const choice = document.createElement("label");
      choice.className = "opt-choice";
      choice._mod = mod;

      const input = document.createElement("input");
      input.type = multi ? "checkbox" : "radio";
      input.name = uid;

      const nested = document.createElement("div");
      nested.className = "opt-nested";
      choice._nested = nested;

      input.onchange = () => {
        if (multi) {
          const checked = wrap.querySelectorAll(":scope > .opt-choice > input:checked");
          if (checked.length > group.max) { input.checked = false; return; }
          choice.classList.toggle("selected", input.checked);
          nested.innerHTML = "";
          if (input.checked && mod.modgrps && mod.modgrps.length) renderGroups(mod.modgrps, nested);
        } else {
          // radio : ne garder que ce choix, réinitialiser les voisins
          wrap.querySelectorAll(":scope > .opt-choice").forEach((c) => {
            c.classList.remove("selected");
            if (c._nested) c._nested.innerHTML = "";
          });
          choice.classList.add("selected");
          nested.innerHTML = "";
          if (mod.modgrps && mod.modgrps.length) renderGroups(mod.modgrps, nested);
        }
      };

      choice.appendChild(input);
      const nm = document.createElement("span");
      nm.className = "oc-name";
      nm.textContent = mod.name;
      choice.appendChild(nm);

      wrap.appendChild(choice);
      wrap.appendChild(nested);

      // Pré-sélection : groupe obligatoire à option unique.
      if (!multi && min >= 1 && group.modifiers.length === 1) {
        input.checked = true;
        input.dispatchEvent(new Event("change"));
      }
    });

    container.appendChild(wrap);
  });
}

function closeOptions() {
  $("options-overlay").hidden = true;
  state.currentItem = null;
}

/* Première option obligatoire non satisfaite (ou null). */
function firstUnmet(container) {
  const groups = container.querySelectorAll(":scope > .opt-group");
  for (const wrap of groups) {
    const group = wrap._group;
    const min = group.min || 0;
    const checked = wrap.querySelectorAll(":scope > .opt-choice > input:checked");
    if (min >= 1 && checked.length < min) return group.name;
    for (const choice of wrap.querySelectorAll(":scope > .opt-choice")) {
      const input = choice.querySelector("input");
      if (input.checked && choice._nested) {
        const sub = firstUnmet(choice._nested);
        if (sub) return sub;
      }
    }
  }
  return null;
}

/* Construit le payload modgrps (récursif) à partir des sélections. */
function buildFromContainer(container) {
  const result = [];
  container.querySelectorAll(":scope > .opt-group").forEach((wrap) => {
    const group = wrap._group;
    const modifiers = [];
    wrap.querySelectorAll(":scope > .opt-choice").forEach((choice) => {
      const input = choice.querySelector("input");
      if (!input || !input.checked) return;
      const mod = choice._mod;
      const qty = group.max > 1 ? 1 : group.max;
      const m = {
        id: mod.id,
        unitPrice: mod.price != null ? mod.price : 0,
        quantity: qty,
      };
      if (choice._nested && choice._nested.querySelector(":scope > .opt-group")) {
        m.modgrps = buildFromContainer(choice._nested);
      }
      modifiers.push(m);
    });
    if (modifiers.length) result.push({ id: group.id, modifiers });
  });
  return result;
}

async function confirmOptions() {
  const item = state.currentItem;
  if (!item) return;
  const unmet = firstUnmet($("options-body"));
  if (unmet) {
    toast(`Choisissez : ${unmet}`);
    return;
  }
  const modgrps = buildFromContainer($("options-body"));
  await addItem(item.id, modgrps);
  closeOptions();
}

/* ---------- Ajout au panier ---------- */
async function addItem(itemId, modgrps) {
  try {
    const data = await api("/api/add-item", { itemId, modgrps });
    toast("Ajouté au panier");
    if (data.points != null) state.points = data.points;
    if (data.pointsLimit != null) state.pointsLimit = data.pointsLimit;
    applyCanAddFlags(data.canAddByItemId);
    await refreshCart();
  } catch (e) {
    toast(e.message);
  }
}

/* ---------- Panier ---------- */
async function refreshCart() {
  try {
    const data = await api("/api/basket");
    state.cartCount = data.items.reduce((n, it) => n + (it.quantity || 1), 0);
    const badge = $("cart-badge");
    if (state.cartCount > 0) {
      badge.hidden = false;
      badge.textContent = state.cartCount;
    } else {
      badge.hidden = true;
    }
    state.points = data.points || 0;
    if (data.pointsLimit != null) state.pointsLimit = data.pointsLimit;
    applyCanAddFlags(data.canAddByItemId);
    renderCart(data);
    refreshMenuLimits();
  } catch (e) {
    /* silencieux */
  }
}

/** Applique les flags canAdd fournis par le backend (aucune regle metier locale). */
function applyCanAddFlags(canAddByItemId) {
  if (!canAddByItemId || typeof canAddByItemId !== "object") return;
  state.categories = (state.categories || []).map((cat) => ({
    ...cat,
    items: (cat.items || []).map((it) => {
      const key = String(it.id);
      if (!(key in canAddByItemId)) return it;
      if (it.available === false || it.price == null) {
        return { ...it, canAdd: false };
      }
      return { ...it, canAdd: !!canAddByItemId[key] };
    }),
  }));
}

/* Affiche le solde client (valeur serveur) — jamais utilise pour autoriser un paiement. */
function setBalance(balance, currency) {
  state.balance = balance;
  state.currency = currency || "EUR";
  const el = $("balance-value");
  if (el) el.textContent = `${Number(balance).toFixed(2)} ${state.currency}`;
}

function renderCart(data) {
  const list = $("cart-items");
  list.innerHTML = "";
  const currency = data.currency || state.currency || "EUR";
  if (!data.items.length) {
    $("cart-empty").hidden = false;
    $("go-checkout").disabled = true;
  } else {
    $("cart-empty").hidden = true;
    $("go-checkout").disabled = false;
    data.items.forEach((it) => {
      const row = document.createElement("div");
      row.className = "cart-row";
      const price =
        it.price != null
          ? `<span class="c-pts">${Number(it.price).toFixed(2)} ${currency}</span>`
          : "";
      const opts = (it.options && it.options.length)
        ? `<div class="c-opts">${escapeHtml(it.options.join(" · "))}</div>`
        : "";
      row.innerHTML = `
        <div class="c-main"><span class="c-qty">${it.quantity || 1}×</span>${escapeHtml(it.name)}${opts}</div>
        <div class="c-right">${price}<button class="c-remove" aria-label="Retirer"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>`;
      row.querySelector(".c-remove").onclick = () => removeItem(it.id);
      list.appendChild(row);
    });
  }
  const total = data.total != null ? Number(data.total) : 0;
  $("cart-total").textContent = data.items.length
    ? `${total.toFixed(2)} ${currency}`
    : "—";
}

async function removeItem(itemUUID) {
  try {
    await api("/api/remove-item", { itemUUID });
    refreshCart();
  } catch (e) {
    toast(e.message);
  }
}

/* ---------- Commande ---------- */
async function checkout() {
  $("go-checkout").disabled = true;
  toast("Validation du panier…");
  try {
    const data = await api("/api/checkout", {});
    if (data.balance != null) {
      setBalance(data.balance, data.currency || state.currency || "EUR");
    }
    showScreen("confirm");
    renderConfirm(data);
  } catch (e) {
    toast(e.message);
    $("go-checkout").disabled = false;
  }
}

function renderConfirm(data) {
  state.lastOrder = {
    number: data.orderNumber,
    uuid: data.orderUUID,
    state: "confirmée",
  };
  const box = $("confirm-box");
  const total =
    data.total != null
      ? `<p class="info-note">Total : ${Number(data.total).toFixed(2)} ${escapeHtml(data.currency || "EUR")}</p>`
      : "";
  box.innerHTML = `
    <p>Panier validé.</p>
    <div class="order-num">N° ${escapeHtml(String(data.orderNumber || "—"))}</div>
    ${total}
    <p class="info-note">Aucune commande KFC automatique — panier enregistré localement.</p>
    <button class="secondary-btn" id="back-menu">Nouvelle commande</button>`;
  $("back-menu").onclick = () => {
    backToSearch();
  };
}

/* ---------- Utilitaires ---------- */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/* ---------- Câblage ---------- */
$("search-btn").onclick = doSearch;
$("search-input").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });
$("options-close").onclick = closeOptions;
$("options-overlay").onclick = (e) => { if (e.target === $("options-overlay")) closeOptions(); };
$("options-add").onclick = confirmOptions;
$("cart-btn").onclick = () => { setNav(null); showScreen("cart"); refreshCart(); };
$("go-checkout").onclick = checkout;
$("back-to-search").onclick = backToSearch;
$("points-limit-close").onclick = closePointsLimitOverlay;
$("points-limit-overlay").onclick = (e) => {
  if (e.target === $("points-limit-overlay")) closePointsLimitOverlay();
};

/* Retour à la recherche pour choisir un autre restaurant. */
function backToSearch() {
  state.menuLoaded = false;
  state.categories = [];
  state.points = 0;
  const badge = $("cart-badge");
  if (badge) badge.hidden = true;
  const banner = $("points-limit-banner");
  if (banner) banner.hidden = true;
  closePointsLimitOverlay();
  setNav("boutique");
  showScreen("search");
  $("search-input").focus();
}

document.querySelectorAll(".nav-item").forEach((n) => {
  n.onclick = () => {
    const nav = n.dataset.nav;
    setNav(nav);
    if (nav === "boutique") {
      showScreen(state.menuLoaded ? "menu" : "search");
    } else if (nav === "portefeuille") {
      renderWallet();
      showScreen("portefeuille");
    } else if (nav === "historique") {
      renderHistory();
      showScreen("historique");
    } else if (nav === "ma-commande") {
      renderMaCommande();
      showScreen("ma-commande");
    } else if (nav === "sav") {
      showScreen("sav");
    } else if (nav === "commande") {
      // Affichage seul : le backend renvoie 403 si non-admin.
      renderAdminOrders();
      showScreen("commande");
    } else if (nav === "paiement") {
      state.adminPaiementId = null;
      renderAdminPaiements();
      showScreen("paiement");
    } else if (nav === "gestion") {
      state.gestionResource = null;
      renderGestionHub();
      showScreen("gestion");
    }
  };
});

function setAdminNav(showAdmin) {
  state.showAdmin = !!showAdmin;
  ["nav-commande", "nav-paiement", "nav-gestion"].forEach((id) => {
    const btn = $(id);
    if (btn) btn.hidden = !state.showAdmin;
  });
  document.body.classList.toggle("is-admin", state.showAdmin);
}

function setMaCommandeNav(visible) {
  state.hasMaCommande = !!visible;
  const btn = $("nav-ma-commande");
  if (btn) btn.hidden = !state.hasMaCommande;
}

function renderAdminOrders() {
  const list = $("admin-orders-list");
  const empty = $("admin-orders-empty");
  if (!list || !empty) return;
  list.innerHTML = "";
  empty.hidden = false;
  empty.textContent = "Chargement…";

  api("/api/admin/orders")
    .then((data) => {
      list.innerHTML = "";
      const orders = data.orders || [];
      if (!orders.length) {
        empty.textContent = "File vide.";
        empty.hidden = false;
        return;
      }
      empty.hidden = true;
      orders.forEach((o) => {
        const row = document.createElement("button");
        row.type = "button";
        row.className = "queue-item queue-item-btn";
        row.textContent = o.label || `${o.clientName || "—"} - ${o.orderNumber || o.id || "—"}`;
        row.onclick = () => openAdminOrderDetail(o.id);
        list.appendChild(row);
      });
    })
    .catch((e) => {
      empty.textContent = e.message || "Impossible de charger la file.";
      empty.hidden = false;
    });
}

function openAdminOrderDetail(orderId) {
  state.adminOrderId = orderId;
  const box = $("admin-order-detail");
  if (box) box.innerHTML = "<p class='info-note'>Chargement…</p>";
  $("admin-cancel-panel").hidden = true;
  $("admin-complete-panel").hidden = false;
  $("admin-cancel-btn").hidden = false;
  ["admin-f-prenom", "admin-f-resto", "admin-f-heure", "admin-f-preuve"].forEach((id) => {
    const el = $(id);
    if (el) el.value = "";
  });
  const expl = $("admin-cancel-expl");
  if (expl) expl.value = "";
  showScreen("commande-detail");

  api(`/api/admin/orders/${orderId}`)
    .then((data) => {
      const o = data.order;
      if (!o) throw new Error("Commande introuvable");
      const items = (o.items || [])
        .map((it) => `• ${it.quantity || 1}× ${it.name || it.loyaltyId || "?"}`)
        .join("\n");
      const place = [o.storeName, o.storeCity].filter(Boolean).join(" · ");
      box.innerHTML = `
        <div class="info-line"><span>N°</span><span>${escapeHtml(String(o.orderNumber || o.id))}</span></div>
        <p class="info-note">Resto : ${escapeHtml(place || "—")}</p>
        <p class="info-note">Points : ${escapeHtml(String(o.totalPoints != null ? o.totalPoints : "—"))}</p>
        <p class="info-note">Total : ${o.totalEur != null ? escapeHtml(Number(o.totalEur).toFixed(2)) + " EUR" : "—"}</p>
        <p class="info-note">User #${escapeHtml(String(o.userId != null ? o.userId : "—"))}</p>
        <pre class="order-items-pre">${escapeHtml(items || "Aucun article")}</pre>`;
    })
    .catch((e) => {
      toast(e.message || "Erreur");
      showScreen("commande");
    });
}

function openAdminUserInfo() {
  if (!state.adminOrderId) return;
  const box = $("admin-user-box");
  if (box) box.innerHTML = "<p class='info-note'>Chargement…</p>";
  showScreen("commande-user");
  api(`/api/admin/orders/${state.adminOrderId}/user`)
    .then((data) => {
      const u = data.user || {};
      box.innerHTML = `
        <div class="info-line"><span>ID</span><span>${escapeHtml(String(u.id ?? "—"))}</span></div>
        <div class="info-line"><span>Telegram</span><span>${escapeHtml(String(u.telegramId ?? "—"))}</span></div>
        <div class="info-line"><span>Username</span><span>${escapeHtml(u.username ? "@" + u.username : "—")}</span></div>
        <div class="info-line"><span>Prenom</span><span>${escapeHtml(u.firstName || "—")}</span></div>
        <div class="info-line"><span>Nom</span><span>${escapeHtml(u.lastName || "—")}</span></div>
        <div class="info-line"><span>Solde</span><span>${escapeHtml(u.balance != null ? Number(u.balance).toFixed(2) + " EUR" : "—")}</span></div>
        <div class="info-line"><span>Achats</span><span>${escapeHtml(String(u.purchaseCount ?? "—"))}</span></div>
        <p class="info-note">Dernier achat : ${escapeHtml(u.lastPurchaseAt || "—")}</p>`;
    })
    .catch((e) => {
      toast(e.message || "Erreur user info");
      showScreen("commande-detail");
    });
}

async function adminCompleteOrder() {
  if (!state.adminOrderId) return;
  const btn = $("admin-complete-btn");
  if (btn) btn.disabled = true;
  try {
    await api(`/api/admin/orders/${state.adminOrderId}/complete`, {
      prenom: ($("admin-f-prenom") || {}).value || "",
      restaurant: ($("admin-f-resto") || {}).value || "",
      heureMax: ($("admin-f-heure") || {}).value || "",
      lienPreuve: ($("admin-f-preuve") || {}).value || "",
    });
    toast("Commande terminee");
    state.adminOrderId = null;
    renderAdminOrders();
    showScreen("commande");
    setNav("commande");
  } catch (e) {
    toast(e.message || "Echec");
  } finally {
    if (btn) btn.disabled = false;
  }
}

function revokePreuveObjectUrls() {
  (state._preuveObjectUrls || []).forEach((u) => {
    try { URL.revokeObjectURL(u); } catch (e) {}
  });
  state._preuveObjectUrls = [];
}

async function fetchAuthBlob(path) {
  const opt = {
    headers: {
      "X-Telegram-Init-Data": (tg && tg.initData) ? tg.initData : "",
    },
  };
  const r = await fetch(path, opt);
  if (!r.ok) {
    let data = {};
    try { data = await r.json(); } catch (e) {}
    throw new Error(data.error || `Erreur ${r.status}`);
  }
  return r.blob();
}

function renderAdminPaiements() {
  const list = $("admin-paiements-list");
  const empty = $("admin-paiements-empty");
  if (!list || !empty) return;
  list.innerHTML = "";
  empty.hidden = false;
  empty.textContent = "Chargement…";

  api("/api/admin/paiements")
    .then((data) => {
      list.innerHTML = "";
      const rows = data.paiements || [];
      if (!rows.length) {
        empty.textContent = "File vide.";
        empty.hidden = false;
        return;
      }
      empty.hidden = true;
      rows.forEach((p) => {
        const row = document.createElement("button");
        row.type = "button";
        row.className = "queue-item queue-item-btn";
        row.textContent = p.label || `${p.clientName || "—"} - ${p.id || "—"}`;
        row.onclick = () => openAdminPaiementDetail(p.id);
        list.appendChild(row);
      });
    })
    .catch((e) => {
      empty.textContent = e.message || "Impossible de charger la file.";
      empty.hidden = false;
    });
}

function openAdminPaiementDetail(demandeId) {
  state.adminPaiementId = demandeId;
  revokePreuveObjectUrls();
  const box = $("admin-paiement-detail");
  const preuvesBox = $("admin-paiement-preuves");
  if (box) box.innerHTML = "<p class='info-note'>Chargement…</p>";
  if (preuvesBox) preuvesBox.innerHTML = "";
  showScreen("paiement-detail");

  api(`/api/admin/paiements/${demandeId}`)
    .then(async (data) => {
      const p = data.paiement;
      if (!p) throw new Error("Demande introuvable");
      const cur = p.currency || "EUR";
      box.innerHTML = `
        <div class="info-line"><span>N°</span><span>${escapeHtml(String(p.id))}</span></div>
        <div class="info-line"><span>Client</span><span>${escapeHtml(p.clientName || "—")}</span></div>
        <div class="info-line"><span>Montant</span><span>${p.montant != null ? escapeHtml(Number(p.montant).toFixed(2) + " " + cur) : "—"}</span></div>
        <div class="info-line"><span>Moyen</span><span>${escapeHtml(p.moyenNom || "—")}</span></div>
        <p class="info-note">Lien : ${escapeHtml(p.lien || "—")}</p>
        <p class="info-note">Finalise : ${escapeHtml(p.finalizedAt || "—")}</p>
        <p class="info-note">Preuves : ${escapeHtml(String(p.preuveCount != null ? p.preuveCount : (p.preuves || []).length))}</p>`;

      if (preuvesBox) {
        preuvesBox.innerHTML = "";
        const preuves = p.preuves || [];
        if (!preuves.length) {
          preuvesBox.innerHTML = `<p class="info-note">Aucune preuve.</p>`;
        } else {
          for (const pr of preuves) {
            const wrap = document.createElement("div");
            wrap.className = "admin-preuve-item";
            wrap.innerHTML = `<div class="c-opts">${escapeHtml(pr.filename || "preuve")}</div>`;
            try {
              const blob = await fetchAuthBlob(pr.url);
              const url = URL.createObjectURL(blob);
              state._preuveObjectUrls.push(url);
              const mime = (pr.mime || blob.type || "").toLowerCase();
              if (mime.includes("pdf")) {
                const a = document.createElement("a");
                a.href = url;
                a.target = "_blank";
                a.rel = "noopener";
                a.className = "secondary-btn";
                a.textContent = "Ouvrir PDF";
                wrap.appendChild(a);
              } else {
                const img = document.createElement("img");
                img.className = "admin-preuve-img";
                img.src = url;
                img.alt = pr.filename || "preuve";
                wrap.appendChild(img);
              }
            } catch (e) {
              const err = document.createElement("p");
              err.className = "info-note";
              err.textContent = e.message || "Preuve indisponible";
              wrap.appendChild(err);
            }
            preuvesBox.appendChild(wrap);
          }
        }
      }
    })
    .catch((e) => {
      toast(e.message || "Erreur");
      showScreen("paiement");
    });
}

function openAdminPaiementUserInfo() {
  if (!state.adminPaiementId) return;
  const box = $("admin-paiement-user-box");
  if (box) box.innerHTML = "<p class='info-note'>Chargement…</p>";
  showScreen("paiement-user");
  api(`/api/admin/paiements/${state.adminPaiementId}/user`)
    .then((data) => {
      const u = data.user || {};
      box.innerHTML = `
        <div class="info-line"><span>ID</span><span>${escapeHtml(String(u.id ?? "—"))}</span></div>
        <div class="info-line"><span>Telegram</span><span>${escapeHtml(String(u.telegramId ?? "—"))}</span></div>
        <div class="info-line"><span>Username</span><span>${escapeHtml(u.username ? "@" + u.username : "—")}</span></div>
        <div class="info-line"><span>Prenom</span><span>${escapeHtml(u.firstName || "—")}</span></div>
        <div class="info-line"><span>Nom</span><span>${escapeHtml(u.lastName || "—")}</span></div>
        <div class="info-line"><span>Solde</span><span>${escapeHtml(u.balance != null ? Number(u.balance).toFixed(2) + " EUR" : "—")}</span></div>
        <div class="info-line"><span>Achats</span><span>${escapeHtml(String(u.purchaseCount ?? "—"))}</span></div>
        <p class="info-note">Dernier achat : ${escapeHtml(u.lastPurchaseAt || "—")}</p>`;
    })
    .catch((e) => {
      toast(e.message || "Erreur user info");
      showScreen("paiement-detail");
    });
}

async function adminAcceptPaiement() {
  if (!state.adminPaiementId) return;
  if (!confirm("Accepter et crediter le solde ?")) return;
  const btn = $("admin-paiement-accept");
  if (btn) btn.disabled = true;
  try {
    await api(`/api/admin/paiements/${state.adminPaiementId}/accept`, {});
    toast("Paiement accepte");
    state.adminPaiementId = null;
    revokePreuveObjectUrls();
    renderAdminPaiements();
    showScreen("paiement");
    setNav("paiement");
  } catch (e) {
    toast(e.message || "Echec");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function adminRejectPaiement() {
  if (!state.adminPaiementId) return;
  if (!confirm("Refuser cette demande ?")) return;
  const btn = $("admin-paiement-reject");
  if (btn) btn.disabled = true;
  try {
    await api(`/api/admin/paiements/${state.adminPaiementId}/reject`, {});
    toast("Paiement refuse");
    state.adminPaiementId = null;
    revokePreuveObjectUrls();
    renderAdminPaiements();
    showScreen("paiement");
    setNav("paiement");
  } catch (e) {
    toast(e.message || "Echec");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function adminCancelOrder() {
  if (!state.adminOrderId) return;
  const expl = String(($("admin-cancel-expl") || {}).value || "").trim();
  if (!expl) {
    toast("Explication requise");
    return;
  }
  const btn = $("admin-cancel-finalize");
  if (btn) btn.disabled = true;
  try {
    await api(`/api/admin/orders/${state.adminOrderId}/cancel`, { explication: expl });
    toast("Commande annulee — solde rembourse");
    state.adminOrderId = null;
    renderAdminOrders();
    showScreen("commande");
    setNav("commande");
  } catch (e) {
    toast(e.message || "Echec annulation");
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderOrderCardHtml(o) {
  if (!o) return "<p class='info-note'>Aucune commande.</p>";
  const items = (o.items || [])
    .map((it) => `• ${it.quantity || 1}× ${escapeHtml(it.name || it.loyaltyId || "?")}`)
    .join("<br/>");
  const place = [o.storeName, o.storeCity].filter(Boolean).join(" · ");
  let extra = "";
  if (o.annulee) {
    extra = `<div class="ma-commande-banner cancel">Commande annulee</div>
      <p class="info-note">${escapeHtml(o.annulationExplication || "")}</p>`;
  } else if (o.terminer) {
    const rows = [
      o.adminPrenom ? `<div class="info-line"><span>Prenom</span><span>${escapeHtml(o.adminPrenom)}</span></div>` : "",
      o.adminRestaurant ? `<div class="info-line"><span>Restaurant</span><span>${escapeHtml(o.adminRestaurant)}</span></div>` : "",
      o.adminHeureMax ? `<div class="info-line"><span>Heure max</span><span>${escapeHtml(o.adminHeureMax)}</span></div>` : "",
      o.adminLienPreuve
        ? `<p class="info-note"><a href="${escapeHtml(o.adminLienPreuve)}" target="_blank" rel="noopener">Lien de preuve</a></p>`
        : "",
    ].join("");
    extra = `<div class="ma-commande-banner ok">Commande terminee</div>${rows}`;
  }
  return `
    <div class="info-card ma-commande-card">
      ${extra}
      <div class="info-line"><span>N°</span><span>${escapeHtml(String(o.orderNumber || o.id || "—"))}</span></div>
      <p class="info-note">${escapeHtml(place || "—")}</p>
      <p class="info-note">${o.totalEur != null ? escapeHtml(Number(o.totalEur).toFixed(2)) + " EUR" : ""} ${o.totalPoints != null ? "· " + escapeHtml(String(o.totalPoints)) + " pts" : ""}</p>
      <div class="ma-commande-items">${items || "—"}</div>
    </div>`;
}

function renderMaCommande() {
  const box = $("ma-commande-box");
  const empty = $("ma-commande-empty");
  if (!box) return;
  box.innerHTML = "";
  if (empty) {
    empty.hidden = false;
    empty.textContent = "Chargement…";
  }
  api("/api/ma-commande")
    .then((data) => {
      setMaCommandeNav(!!data.hasMaCommande);
      if (!data.order) {
        box.innerHTML = "";
        if (empty) {
          empty.textContent = "Aucune commande a consulter.";
          empty.hidden = false;
        }
        return;
      }
      if (empty) empty.hidden = true;
      box.innerHTML = renderOrderCardHtml(data.order);
    })
    .catch((e) => {
      if (empty) {
        empty.textContent = e.message || "Erreur";
        empty.hidden = false;
      }
    });
}

function formatWalletDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return escapeHtml(String(iso));
  return d.toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function apiUpload(path, formData) {
  const opt = {
    method: "POST",
    headers: {
      "X-Telegram-Init-Data": (tg && tg.initData) ? tg.initData : "",
    },
    body: formData,
  };
  if (typeof window !== "undefined" && window.KFC_DEV_TELEGRAM_ID) {
    opt.headers["X-Dev-Telegram-Id"] = String(window.KFC_DEV_TELEGRAM_ID);
  }
  const r = await fetch(path, opt);
  let data = {};
  try { data = await r.json(); } catch (e) {}
  if (!r.ok) {
    const err = new Error(data.error || `Erreur ${r.status}`);
    err.code = data.code || null;
    err.status = r.status;
    err.payload = data;
    throw err;
  }
  return data;
}

function openMoyensModal() {
  const overlay = $("moyens-overlay");
  const body = $("moyens-body");
  const empty = $("moyens-empty");
  body.innerHTML = "";
  empty.hidden = true;

  const moyens = state.walletMoyens || [];
  if (!moyens.length) {
    empty.hidden = false;
  } else {
    moyens.forEach((m) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "moyen-pick-btn";
      btn.textContent = m.nom || "Moyen de paiement";
      btn.onclick = () => startTopup(m);
      body.appendChild(btn);
    });
  }
  overlay.hidden = false;
}

function closeMoyensModal() {
  const overlay = $("moyens-overlay");
  if (overlay) overlay.hidden = true;
}

async function startTopup(moyen) {
  closeMoyensModal();
  toast("Ouverture…");
  try {
    const data = await api("/api/wallet/topup/start", { moyenId: moyen.id });
    const dem = data.demande;
    if (!dem || !dem.id) throw new Error("Demande invalide");
    state.topupDemandeId = dem.id;
    state.topupDemande = dem;
    state.topupMontant = null;
    showTopupMontantPage(dem);
  } catch (e) {
    toast(e.message || "Impossible de demarrer le paiement");
  }
}

const TOPUP_MONTANT_MIN = 1;
const TOPUP_MONTANT_MAX = 10000;

function parseTopupMontantRaw(raw) {
  const s = String(raw || "").trim().replace(",", ".");
  if (!s) return { ok: false, value: NaN };
  // 2 decimales max, format numerique strict
  if (!/^\d+(\.\d{1,2})?$/.test(s)) return { ok: false, value: NaN };
  const v = Number(s);
  if (!Number.isFinite(v)) return { ok: false, value: NaN };
  if (v < TOPUP_MONTANT_MIN || v > TOPUP_MONTANT_MAX) return { ok: false, value: v };
  // force 2 decimales exactes (1.2 ok -> 1.20 conceptuellement)
  const cents = Math.round(v * 100);
  if (Math.abs(v * 100 - cents) > 1e-9) return { ok: false, value: v };
  return { ok: true, value: cents / 100 };
}

function validateTopupMontantLive() {
  const el = $("topup-montant");
  const err = $("topup-montant-error");
  const btn = $("topup-montant-continue");
  const raw = el ? String(el.value || "").trim() : "";
  if (!raw) {
    if (err) err.hidden = true;
    if (btn) btn.disabled = true;
    return false;
  }
  const parsed = parseTopupMontantRaw(raw);
  if (err) err.hidden = parsed.ok;
  if (!parsed.ok && err) {
    err.hidden = false;
    err.textContent = "montant invalide";
  }
  if (btn) btn.disabled = !parsed.ok;
  return parsed.ok;
}

function showTopupMontantPage(dem) {
  const title = $("topup-montant-title");
  if (title) title.textContent = dem.moyenNom || "Montant";
  const el = $("topup-montant");
  if (el) {
    el.value = state.topupMontant != null ? Number(state.topupMontant).toFixed(2) : "";
  }
  validateTopupMontantLive();
  showScreen("topup-montant");
  if (el) el.focus();
}

async function continueTopupMontant() {
  if (!state.topupDemandeId) return;
  if (!validateTopupMontantLive()) {
    toast("montant invalide");
    return;
  }
  const parsed = parseTopupMontantRaw(($("topup-montant") || {}).value);
  const btn = $("topup-montant-continue");
  if (btn) btn.disabled = true;
  try {
    const data = await api(`/api/wallet/topup/${state.topupDemandeId}/montant`, {
      montant: parsed.value,
    });
    state.topupMontant = parsed.value;
    state.topupDemande = data.demande || state.topupDemande;
    showTopupPage(state.topupDemande, data.preuves || []);
  } catch (e) {
    toast(e.message || "montant invalide");
    validateTopupMontantLive();
  }
}

function showTopupPage(dem, preuves) {
  state.topupDemande = dem || state.topupDemande;
  $("topup-title").textContent = (dem && dem.moyenNom) || "Paiement";
  const lienEl = $("topup-lien");
  const lien = ((dem && dem.lien) || "").trim();
  if (lien) {
    lienEl.href = lien;
    lienEl.textContent = lien;
    lienEl.hidden = false;
  } else {
    lienEl.removeAttribute("href");
    lienEl.textContent = "Lien non configure";
    lienEl.hidden = false;
  }
  const recap = $("topup-montant-recap");
  const m = state.topupMontant != null ? state.topupMontant : (dem && dem.montant);
  if (recap) {
    recap.textContent =
      m != null ? `Montant : ${Number(m).toFixed(2)} EUR` : "";
  }
  renderTopupPreuves(preuves || []);
  showScreen("topup");
}

function updateTopupFinalizeState(preuveCount) {
  const fin = $("topup-finalize");
  if (!fin) return;
  const m = state.topupMontant;
  fin.disabled = !(
    preuveCount > 0 &&
    m != null &&
    Number.isFinite(m) &&
    m >= TOPUP_MONTANT_MIN &&
    m <= TOPUP_MONTANT_MAX
  );
}

function renderTopupPreuves(preuves) {
  const list = $("topup-preuves");
  const empty = $("topup-preuves-empty");
  list.innerHTML = "";
  const items = preuves || [];
  if (!items.length) {
    empty.hidden = false;
  } else {
    empty.hidden = true;
    items.forEach((p, i) => {
      const row = document.createElement("div");
      row.className = "topup-preuve-item";
      row.textContent = p.filename || `Preuve ${i + 1}`;
      list.appendChild(row);
    });
  }
  updateTopupFinalizeState(items.length);
}

async function refreshTopup() {
  if (!state.topupDemandeId) return;
  const data = await api(`/api/wallet/topup/${state.topupDemandeId}`);
  if (data.demande && data.demande.montant != null) {
    state.topupMontant = Number(data.demande.montant);
  }
  showTopupPage(data.demande, data.preuves || []);
}

async function uploadTopupPreuves(fileList) {
  if (!state.topupDemandeId) return;
  const files = Array.from(fileList || []);
  if (!files.length) return;
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  toast("Envoi des preuves…");
  try {
    const data = await apiUpload(
      `/api/wallet/topup/${state.topupDemandeId}/preuve`,
      fd
    );
    renderTopupPreuves(data.preuves || []);
    toast("Preuve(s) ajoutee(s)");
  } catch (e) {
    toast(e.message || "Echec de l'envoi");
  }
}

async function finalizeTopup() {
  if (!state.topupDemandeId) return;
  const montant = state.topupMontant;
  if (
    montant == null ||
    !Number.isFinite(montant) ||
    montant < TOPUP_MONTANT_MIN ||
    montant > TOPUP_MONTANT_MAX
  ) {
    toast("montant invalide");
    showTopupMontantPage(state.topupDemande || {});
    return;
  }
  const btn = $("topup-finalize");
  btn.disabled = true;
  toast("Finalisation…");
  try {
    await api(`/api/wallet/topup/${state.topupDemandeId}/finalize`, { montant });
    state.topupDemandeId = null;
    state.topupMontant = null;
    state.topupDemande = null;
    showScreen("topup-done");
  } catch (e) {
    toast(e.message || "Finalisation impossible");
    try { await refreshTopup(); } catch (_) {}
  }
}

function renderWallet() {
  const balEl = $("wallet-balance");
  const paysEl = $("wallet-paiements");
  const paysEmpty = $("wallet-paiements-empty");

  if (balEl) balEl.textContent = "…";
  paysEl.innerHTML = "";
  paysEmpty.hidden = false;
  paysEmpty.textContent = "Chargement…";

  api("/api/wallet")
    .then((data) => {
      const cur = data.currency || state.currency || "EUR";
      state.walletMoyens = data.moyens || [];
      if (data.balance != null) {
        setBalance(data.balance, cur);
      }
      if (balEl) {
        balEl.textContent = `${Number(data.balance != null ? data.balance : 0).toFixed(2)} ${cur}`;
      }

      const paiements = data.paiements || [];
      paysEl.innerHTML = "";
      if (!paiements.length) {
        paysEmpty.textContent = "Aucun paiement pour le moment.";
        paysEmpty.hidden = false;
        return;
      }
      paysEmpty.hidden = true;
      paiements.forEach((p) => {
        const row = document.createElement("div");
        row.className = "cart-row wallet-pay-row";
        const pending = p.status === "PENDING";
        const rejected = p.status === "REJECTED";
        const montant =
          p.solde == null
            ? (pending ? "En attente" : "—")
            : `${Number(p.solde).toFixed(2)} ${cur}`;
        const statusHint = pending
          ? " · en attente"
          : rejected
            ? " · refuse"
            : "";
        row.innerHTML = `
          <div class="c-main">
            <div>${escapeHtml(p.moyen || "—")}</div>
            <div class="c-opts">${formatWalletDate(p.date)}${statusHint}</div>
          </div>
          <div class="c-right">
            <span class="c-pts">${escapeHtml(montant)}</span>
          </div>`;
        paysEl.appendChild(row);
      });
    })
    .catch((e) => {
      if (balEl) balEl.textContent = "—";
      paysEmpty.textContent = e.message || "Impossible de charger le portefeuille.";
      paysEmpty.hidden = false;
    });
}

/* Bindings portefeuille / topup */
(() => {
  const addBtn = $("btn-add-solde");
  if (addBtn) addBtn.onclick = () => openMoyensModal();
  const moyensClose = $("moyens-close");
  if (moyensClose) moyensClose.onclick = closeMoyensModal;
  const moyensOverlay = $("moyens-overlay");
  if (moyensOverlay) {
    moyensOverlay.addEventListener("click", (e) => {
      if (e.target === moyensOverlay) closeMoyensModal();
    });
  }
  const topupBack = $("topup-back");
  if (topupBack) {
    topupBack.onclick = () => {
      showTopupMontantPage(state.topupDemande || {});
    };
  }
  const montantBack = $("topup-montant-back");
  if (montantBack) {
    montantBack.onclick = () => {
      state.topupDemandeId = null;
      state.topupMontant = null;
      state.topupDemande = null;
      renderWallet();
      showScreen("portefeuille");
    };
  }
  const addPreuve = $("topup-add-preuve");
  const fileInput = $("topup-file");
  if (addPreuve && fileInput) {
    addPreuve.onclick = () => fileInput.click();
    fileInput.onchange = () => {
      uploadTopupPreuves(fileInput.files);
      fileInput.value = "";
    };
  }
  const fin = $("topup-finalize");
  if (fin) fin.onclick = () => finalizeTopup();
  const montantEl = $("topup-montant");
  if (montantEl) {
    montantEl.addEventListener("input", () => validateTopupMontantLive());
  }
  const montantContinue = $("topup-montant-continue");
  if (montantContinue) montantContinue.onclick = () => continueTopupMontant();
  const doneOk = $("topup-done-ok");
  if (doneOk) {
    doneOk.onclick = () => {
      renderWallet();
      showScreen("portefeuille");
      setNav("portefeuille");
    };
  }

  const adminBack = $("admin-order-back");
  if (adminBack) {
    adminBack.onclick = () => {
      state.adminOrderId = null;
      renderAdminOrders();
      showScreen("commande");
      setNav("commande");
    };
  }
  const userInfoBtn = $("admin-user-info-btn");
  if (userInfoBtn) userInfoBtn.onclick = () => openAdminUserInfo();
  const userBack = $("admin-user-back");
  if (userBack) {
    userBack.onclick = () => showScreen("commande-detail");
  }
  const completeBtn = $("admin-complete-btn");
  if (completeBtn) completeBtn.onclick = () => adminCompleteOrder();
  const cancelBtn = $("admin-cancel-btn");
  if (cancelBtn) {
    cancelBtn.onclick = () => {
      $("admin-complete-panel").hidden = true;
      $("admin-cancel-btn").hidden = true;
      $("admin-cancel-panel").hidden = false;
    };
  }
  const cancelAbort = $("admin-cancel-abort");
  if (cancelAbort) {
    cancelAbort.onclick = () => {
      $("admin-cancel-panel").hidden = true;
      $("admin-complete-panel").hidden = false;
      $("admin-cancel-btn").hidden = false;
    };
  }
  const cancelFin = $("admin-cancel-finalize");
  if (cancelFin) cancelFin.onclick = () => adminCancelOrder();

  const payBack = $("admin-paiement-back");
  if (payBack) {
    payBack.onclick = () => {
      state.adminPaiementId = null;
      revokePreuveObjectUrls();
      renderAdminPaiements();
      showScreen("paiement");
      setNav("paiement");
    };
  }
  const payUserBtn = $("admin-paiement-user-btn");
  if (payUserBtn) payUserBtn.onclick = () => openAdminPaiementUserInfo();
  const payUserBack = $("admin-paiement-user-back");
  if (payUserBack) {
    payUserBack.onclick = () => showScreen("paiement-detail");
  }
  const payAccept = $("admin-paiement-accept");
  if (payAccept) payAccept.onclick = () => adminAcceptPaiement();
  const payReject = $("admin-paiement-reject");
  if (payReject) payReject.onclick = () => adminRejectPaiement();

  const gestionBack = $("gestion-back");
  if (gestionBack) {
    gestionBack.onclick = () => {
      state.gestionResource = null;
      renderGestionHub();
      showScreen("gestion");
      setNav("gestion");
    };
  }
})();

/* ---------- Gestion (admin) ---------- */
function renderGestionHub() {
  const box = $("gestion-resources");
  const empty = $("gestion-hub-empty");
  if (!box) return;
  box.innerHTML = "";
  if (empty) {
    empty.hidden = false;
    empty.textContent = "Chargement…";
  }

  const paint = (resources) => {
    box.innerHTML = "";
    if (!resources.length) {
      if (empty) {
        empty.textContent = "Aucune ressource.";
        empty.hidden = false;
      }
      return;
    }
    if (empty) empty.hidden = true;
    resources.forEach((r) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "queue-item queue-item-btn gestion-resource-btn";
      btn.innerHTML = `
        <div class="gestion-res-label">${escapeHtml(r.label)}</div>
        <div class="c-opts">${escapeHtml(r.description || "")}</div>`;
      btn.onclick = () => openGestionResource(r);
      box.appendChild(btn);
    });
  };

  if (state.gestionMeta && state.gestionMeta.length) {
    paint(state.gestionMeta);
    return;
  }

  api("/api/admin/gestion/meta")
    .then((data) => {
      state.gestionMeta = data.resources || [];
      paint(state.gestionMeta);
    })
    .catch((e) => {
      if (empty) {
        empty.textContent = e.message || "Erreur";
        empty.hidden = false;
      }
    });
}

function openGestionResource(res) {
  state.gestionResource = res.id;
  const title = $("gestion-resource-title");
  const desc = $("gestion-resource-desc");
  if (title) title.textContent = res.label || res.id;
  if (desc) desc.textContent = res.description || "";
  const body = $("gestion-body");
  const empty = $("gestion-empty");
  const toolbar = $("gestion-toolbar");
  if (body) body.innerHTML = "";
  if (toolbar) {
    toolbar.innerHTML = "";
    toolbar.hidden = true;
  }
  if (empty) {
    empty.hidden = false;
    empty.textContent = "Chargement…";
  }
  showScreen("gestion-resource");
  setNav("gestion");

  const loaders = {
    config: loadGestionConfig,
    articles: loadGestionArticles,
    blacklist: loadGestionBlacklist,
    moyens: loadGestionMoyens,
    users: loadGestionUsers,
  };
  const fn = loaders[res.id];
  if (!fn) {
    if (empty) empty.textContent = "Ressource inconnue.";
    return;
  }
  fn().catch((e) => {
    if (empty) {
      empty.textContent = e.message || "Erreur";
      empty.hidden = false;
    }
  });
}

function _gestionReady() {
  const empty = $("gestion-empty");
  if (empty) empty.hidden = true;
  return $("gestion-body");
}

async function loadGestionConfig() {
  const data = await api("/api/admin/gestion/config");
  const cfg = data.config || {};
  const body = _gestionReady();
  if (!body) return;
  body.innerHTML = `
    <div class="gestion-form">
      <label class="field-label" for="g-cfg-reduction">Reduction (%)</label>
      <input class="field-input" id="g-cfg-reduction" type="number" min="0" max="100" step="0.1" value="${escapeHtml(String(cfg.reduction ?? ""))}" />
      <label class="field-label" for="g-cfg-currency">Devise</label>
      <input class="field-input" id="g-cfg-currency" type="text" maxlength="8" value="${escapeHtml(cfg.currency || "EUR")}" />
      <label class="field-label" for="g-cfg-version">Version affichee</label>
      <input class="field-input" id="g-cfg-version" type="text" maxlength="32" value="${escapeHtml(cfg.version || "")}" />
      <label class="field-label" for="g-cfg-admin">Admin Telegram ID</label>
      <input class="field-input" id="g-cfg-admin" type="text" inputmode="numeric" value="${escapeHtml(cfg.admin != null ? String(cfg.admin) : "")}" />
      <label class="field-label gestion-check-row">
        <input type="checkbox" id="g-cfg-actif" ${cfg.actif ? "checked" : ""} />
        Shop actif
      </label>
      <label class="field-label" for="g-cfg-ph">Prochaine heure (si inactif)</label>
      <input class="field-input" id="g-cfg-ph" type="text" value="${escapeHtml(cfg.prochaine_heure || "")}" />
      <button class="primary-btn" id="g-cfg-save" type="button">Enregistrer</button>
    </div>`;
  const save = $("g-cfg-save");
  if (save) {
    save.onclick = async () => {
      save.disabled = true;
      try {
        const actif = !!($("g-cfg-actif") || {}).checked;
        const payload = {
          reduction: Number(($("g-cfg-reduction") || {}).value),
          currency: ($("g-cfg-currency") || {}).value || "EUR",
          version: ($("g-cfg-version") || {}).value || "1",
          admin: ($("g-cfg-admin") || {}).value,
          actif,
          prochaineHeure: actif ? null : (($("g-cfg-ph") || {}).value || null),
        };
        await api("/api/admin/gestion/config", payload, "PATCH");
        toast("Variables enregistrees");
        await loadGestionConfig();
      } catch (e) {
        toast(e.message || "Erreur");
      } finally {
        save.disabled = false;
      }
    };
  }
}

async function loadGestionArticles() {
  const toolbar = $("gestion-toolbar");
  if (toolbar) {
    toolbar.hidden = false;
    toolbar.innerHTML = `
      <input class="field-input gestion-search" id="g-art-q" type="search" placeholder="Rechercher…" autocomplete="off" />
      <button class="secondary-btn gestion-toolbar-btn" id="g-art-new" type="button">+ Article</button>`;
  }
  const q = (($("g-art-q") || {}).value || "").trim();
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  const data = await api(`/api/admin/gestion/articles${qs}`);
  const articles = data.articles || [];
  const body = _gestionReady();
  if (!body) return;

  const paintForm = (art) => {
    const isNew = !art || !art.id;
    body.innerHTML = `
      <div class="gestion-form">
        <label class="field-label" for="g-art-kfc">KFC item id</label>
        <input class="field-input" id="g-art-kfc" type="text" value="${escapeHtml((art && art.kfcItemId) || "")}" ${isNew ? "" : ""} />
        <label class="field-label" for="g-art-name">Nom</label>
        <input class="field-input" id="g-art-name" type="text" value="${escapeHtml((art && art.name) || "")}" />
        <label class="field-label" for="g-art-label">Label</label>
        <input class="field-input" id="g-art-label" type="text" value="${escapeHtml((art && art.label) || "")}" />
        <label class="field-label" for="g-art-price">Prix</label>
        <input class="field-input" id="g-art-price" type="number" min="0" step="0.01" value="${escapeHtml(art && art.price != null ? String(art.price) : "")}" />
        <label class="field-label" for="g-art-cost">Points (cost)</label>
        <input class="field-input" id="g-art-cost" type="number" min="0" step="1" value="${escapeHtml(art && art.cost != null ? String(art.cost) : "")}" />
        <button class="primary-btn" id="g-art-save" type="button">${isNew ? "Creer" : "Enregistrer"}</button>
        ${isNew ? "" : '<button class="danger-btn" id="g-art-del" type="button">Supprimer</button>'}
        <button class="secondary-btn" id="g-art-cancel" type="button">Retour liste</button>
      </div>`;
    $("g-art-cancel").onclick = () => loadGestionArticles().catch((e) => toast(e.message));
    $("g-art-save").onclick = async () => {
      const btn = $("g-art-save");
      btn.disabled = true;
      const payload = {
        kfcItemId: ($("g-art-kfc") || {}).value || "",
        name: ($("g-art-name") || {}).value || "",
        label: ($("g-art-label") || {}).value || "",
        price: Number(($("g-art-price") || {}).value),
        cost: ($("g-art-cost") || {}).value === "" ? null : Number(($("g-art-cost") || {}).value),
      };
      try {
        if (isNew) await api("/api/admin/gestion/articles", payload);
        else await api(`/api/admin/gestion/articles/${art.id}`, payload, "PATCH");
        toast(isNew ? "Article cree" : "Article mis a jour");
        await loadGestionArticles();
      } catch (e) {
        toast(e.message || "Erreur");
        btn.disabled = false;
      }
    };
    const del = $("g-art-del");
    if (del) {
      del.onclick = async () => {
        if (!confirm("Supprimer cet article ?")) return;
        try {
          await api(`/api/admin/gestion/articles/${art.id}`, undefined, "DELETE");
          toast("Article supprime");
          await loadGestionArticles();
        } catch (e) {
          toast(e.message || "Erreur");
        }
      };
    }
  };

  if (!articles.length) {
    body.innerHTML = `<div class="empty-hint">Aucun article.</div>`;
  } else {
    const list = document.createElement("div");
    list.className = "queue-list";
    articles.forEach((a) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "queue-item queue-item-btn";
      row.innerHTML = `
        <div class="gestion-res-label">${escapeHtml(a.label || a.name || a.kfcItemId)}</div>
        <div class="c-opts">${escapeHtml(a.kfcItemId || "")} · ${a.price != null ? Number(a.price).toFixed(2) : "—"} · ${a.cost != null ? a.cost + " pts" : "—"}</div>`;
      row.onclick = () => paintForm(a);
      list.appendChild(row);
    });
    body.innerHTML = "";
    body.appendChild(list);
  }

  const search = $("g-art-q");
  if (search) {
    search.onkeydown = (e) => {
      if (e.key === "Enter") loadGestionArticles().catch((err) => toast(err.message));
    };
  }
  const neu = $("g-art-new");
  if (neu) neu.onclick = () => paintForm(null);
}

async function loadGestionBlacklist() {
  const toolbar = $("gestion-toolbar");
  if (toolbar) {
    toolbar.hidden = false;
    toolbar.innerHTML = `
      <input class="field-input" id="g-bl-id" type="text" placeholder="store id" autocomplete="off" />
      <input class="field-input" id="g-bl-name" type="text" placeholder="nom" autocomplete="off" />
      <input class="field-input" id="g-bl-city" type="text" placeholder="ville" autocomplete="off" />
      <button class="secondary-btn gestion-toolbar-btn" id="g-bl-add" type="button">Ajouter</button>`;
  }
  const data = await api("/api/admin/gestion/blacklist");
  const stores = data.stores || [];
  const body = _gestionReady();
  if (!body) return;
  if (!stores.length) {
    body.innerHTML = `<div class="empty-hint">Blacklist vide.</div>`;
  } else {
    const list = document.createElement("div");
    list.className = "queue-list";
    stores.forEach((s) => {
      const row = document.createElement("div");
      row.className = "queue-item gestion-row";
      row.innerHTML = `
        <div class="gestion-row-main">
          <div class="gestion-res-label">${escapeHtml(s.name || s.storeId)}</div>
          <div class="c-opts">${escapeHtml(s.city || "")} · ${escapeHtml(s.storeId)}${s.reason ? " · " + escapeHtml(s.reason) : ""}</div>
        </div>
        <button class="gestion-mini-danger" type="button" data-id="${escapeHtml(s.storeId)}">Retirer</button>`;
      row.querySelector("button").onclick = async () => {
        if (!confirm("Retirer de la blacklist ?")) return;
        try {
          await api(`/api/admin/gestion/blacklist/${encodeURIComponent(s.storeId)}`, undefined, "DELETE");
          toast("Retire");
          await loadGestionBlacklist();
        } catch (e) {
          toast(e.message || "Erreur");
        }
      };
      list.appendChild(row);
    });
    body.innerHTML = "";
    body.appendChild(list);
  }
  const add = $("g-bl-add");
  if (add) {
    add.onclick = async () => {
      const storeId = (($("g-bl-id") || {}).value || "").trim();
      if (!storeId) {
        toast("store id requis");
        return;
      }
      add.disabled = true;
      try {
        await api("/api/admin/gestion/blacklist", {
          storeId,
          name: (($("g-bl-name") || {}).value || "").trim(),
          city: (($("g-bl-city") || {}).value || "").trim(),
          reason: "manual",
        });
        toast("Ajoute");
        await loadGestionBlacklist();
      } catch (e) {
        toast(e.message || "Erreur");
        add.disabled = false;
      }
    };
  }
}

async function loadGestionMoyens() {
  const toolbar = $("gestion-toolbar");
  if (toolbar) {
    toolbar.hidden = false;
    toolbar.innerHTML = `
      <input class="field-input" id="g-moy-nom" type="text" placeholder="Nom" autocomplete="off" />
      <input class="field-input" id="g-moy-lien" type="text" placeholder="Lien" autocomplete="off" />
      <button class="secondary-btn gestion-toolbar-btn" id="g-moy-add" type="button">Ajouter</button>`;
  }
  const data = await api("/api/admin/gestion/moyens");
  const moyens = data.moyens || [];
  const body = _gestionReady();
  if (!body) return;

  const editForm = (m) => {
    body.innerHTML = `
      <div class="gestion-form">
        <label class="field-label" for="g-moy-e-nom">Nom</label>
        <input class="field-input" id="g-moy-e-nom" type="text" value="${escapeHtml(m.nom || "")}" />
        <label class="field-label" for="g-moy-e-lien">Lien</label>
        <input class="field-input" id="g-moy-e-lien" type="text" value="${escapeHtml(m.lien || "")}" />
        <button class="primary-btn" id="g-moy-save" type="button">Enregistrer</button>
        <button class="danger-btn" id="g-moy-del" type="button">Supprimer</button>
        <button class="secondary-btn" id="g-moy-cancel" type="button">Retour liste</button>
      </div>`;
    $("g-moy-cancel").onclick = () => loadGestionMoyens().catch((e) => toast(e.message));
    $("g-moy-save").onclick = async () => {
      try {
        await api(`/api/admin/gestion/moyens/${m.id}`, {
          nom: ($("g-moy-e-nom") || {}).value || "",
          lien: ($("g-moy-e-lien") || {}).value || "",
        }, "PATCH");
        toast("Moyen mis a jour");
        await loadGestionMoyens();
      } catch (e) {
        toast(e.message || "Erreur");
      }
    };
    $("g-moy-del").onclick = async () => {
      if (!confirm("Supprimer ce moyen ?")) return;
      try {
        await api(`/api/admin/gestion/moyens/${m.id}`, undefined, "DELETE");
        toast("Supprime");
        await loadGestionMoyens();
      } catch (e) {
        toast(e.message || "Erreur");
      }
    };
  };

  if (!moyens.length) {
    body.innerHTML = `<div class="empty-hint">Aucun moyen.</div>`;
  } else {
    const list = document.createElement("div");
    list.className = "queue-list";
    moyens.forEach((m) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "queue-item queue-item-btn";
      row.innerHTML = `
        <div class="gestion-res-label">${escapeHtml(m.nom)}</div>
        <div class="c-opts">${escapeHtml(m.lien || "—")}</div>`;
      row.onclick = () => editForm(m);
      list.appendChild(row);
    });
    body.innerHTML = "";
    body.appendChild(list);
  }

  const add = $("g-moy-add");
  if (add) {
    add.onclick = async () => {
      const nom = (($("g-moy-nom") || {}).value || "").trim();
      if (!nom) {
        toast("nom requis");
        return;
      }
      add.disabled = true;
      try {
        await api("/api/admin/gestion/moyens", {
          nom,
          lien: (($("g-moy-lien") || {}).value || "").trim(),
        });
        toast("Moyen ajoute");
        await loadGestionMoyens();
      } catch (e) {
        toast(e.message || "Erreur");
        add.disabled = false;
      }
    };
  }
}

async function loadGestionUsers() {
  const toolbar = $("gestion-toolbar");
  if (toolbar) {
    toolbar.hidden = false;
    toolbar.innerHTML = `
      <input class="field-input gestion-search" id="g-user-q" type="search" placeholder="Telegram / username…" autocomplete="off" />
      <button class="secondary-btn gestion-toolbar-btn" id="g-user-go" type="button">Chercher</button>`;
  }
  const q = (($("g-user-q") || {}).value || "").trim();
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  const data = await api(`/api/admin/gestion/users${qs}`);
  const users = data.users || [];
  const body = _gestionReady();
  if (!body) return;

  const editUser = (u) => {
    body.innerHTML = `
      <div class="gestion-form">
        <div class="info-line"><span>ID</span><span>${escapeHtml(String(u.id))}</span></div>
        <div class="info-line"><span>Telegram</span><span>${escapeHtml(String(u.telegramId))}</span></div>
        <div class="info-line"><span>Username</span><span>${escapeHtml(u.username ? "@" + u.username : "—")}</span></div>
        <label class="field-label" for="g-user-bal">Solde</label>
        <input class="field-input" id="g-user-bal" type="number" min="0" step="0.01" value="${escapeHtml(String(u.balance ?? 0))}" />
        <label class="field-label gestion-check-row">
          <input type="checkbox" id="g-user-active" ${u.isActive ? "checked" : ""} />
          Compte actif
        </label>
        <button class="primary-btn" id="g-user-save" type="button">Enregistrer</button>
        <button class="secondary-btn" id="g-user-cancel" type="button">Retour liste</button>
      </div>`;
    $("g-user-cancel").onclick = () => loadGestionUsers().catch((e) => toast(e.message));
    $("g-user-save").onclick = async () => {
      try {
        await api(`/api/admin/gestion/users/${u.id}`, {
          balance: Number(($("g-user-bal") || {}).value),
          isActive: !!($("g-user-active") || {}).checked,
        }, "PATCH");
        toast("Utilisateur mis a jour");
        await loadGestionUsers();
      } catch (e) {
        toast(e.message || "Erreur");
      }
    };
  };

  if (!users.length) {
    body.innerHTML = `<div class="empty-hint">Aucun utilisateur.</div>`;
  } else {
    const list = document.createElement("div");
    list.className = "queue-list";
    users.forEach((u) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "queue-item queue-item-btn";
      const name = u.firstName || u.username || String(u.telegramId);
      row.innerHTML = `
        <div class="gestion-res-label">${escapeHtml(name)}${u.isActive ? "" : " · inactif"}</div>
        <div class="c-opts">#${escapeHtml(String(u.id))} · ${escapeHtml(String(u.telegramId))} · ${Number(u.balance || 0).toFixed(2)}</div>`;
      row.onclick = () => editUser(u);
      list.appendChild(row);
    });
    body.innerHTML = "";
    body.appendChild(list);
  }

  const go = $("g-user-go");
  if (go) go.onclick = () => loadGestionUsers().catch((e) => toast(e.message));
  const search = $("g-user-q");
  if (search) {
    search.onkeydown = (e) => {
      if (e.key === "Enter") loadGestionUsers().catch((err) => toast(err.message));
    };
  }
}

function renderHistory() {
  const list = $("history-list");
  const empty = $("history-empty");
  list.innerHTML = "";
  empty.hidden = true;
  empty.textContent = "Chargement…";
  empty.hidden = false;

  api("/api/history")
    .then((data) => {
      list.innerHTML = "";
      const orders = data.orders || [];
      if (!orders.length) {
        empty.textContent = "Aucune commande pour le moment.";
        empty.hidden = false;
        return;
      }
      empty.hidden = true;
      orders.forEach((o) => {
        const row = document.createElement("div");
        row.className = "cart-row";
        const pts = o.totalPoints != null ? `${o.totalPoints} pts` : "";
        const eur = o.totalEur != null ? `${Number(o.totalEur).toFixed(2)} EUR` : "";
        const place = [o.storeName, o.storeCity].filter(Boolean).join(" · ");
        let status = o.status || "";
        if (o.annulee) status = "Annulee";
        else if (o.terminer) status = "Terminee";
        else if (!o.terminer) status = "En cours";
        row.innerHTML = `
          <div class="c-main">
            <div>N° ${escapeHtml(String(o.orderNumber || "—"))}</div>
            <div class="c-opts">${escapeHtml(place)}</div>
            ${o.annulee && o.annulationExplication ? `<div class="c-opts">${escapeHtml(o.annulationExplication)}</div>` : ""}
          </div>
          <div class="c-right">
            <span class="c-pts">${escapeHtml(eur || pts)}</span>
            <span style="color:var(--text-dim);font-size:12px">${escapeHtml(status)}</span>
          </div>`;
        list.appendChild(row);
      });
    })
    .catch((e) => {
      empty.textContent = e.message || "Impossible de charger l'historique.";
      empty.hidden = false;
    });
}

/* ---------- Démarrage ---------- */
(async function init() {
  try {
    const me = await api("/api/me");
    setBalance(me.balance != null ? me.balance : 0, me.currency || "EUR");
    setAdminNav(!!me.showAdmin);
    setMaCommandeNav(!!me.hasMaCommande);
    if (me.pointsLimit != null) state.pointsLimit = me.pointsLimit;
    if (me.shopOpen === false) {
      showShopInactive(me.shopMessage, me.prochaineHeure);
      return;
    }
  } catch (e) {
    if (isShopInactiveError(e)) {
      showShopInactive(e.message, e.payload && e.payload.prochaineHeure);
      return;
    }
    setBalance(0, "EUR");
    setAdminNav(false);
    setMaCommandeNav(false);
  }
  showScreen("search");
  setNav("boutique");
})();
