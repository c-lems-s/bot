/* Mini-app KFC — Telegram WebApp multi-user (compte KFC partage cote serveur). */

const tg = window.Telegram ? window.Telegram.WebApp : null;
if (tg) {
  tg.ready();
  tg.expand();
}

const api = async (path, body) => {
  const opt = {
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": (tg && tg.initData) ? tg.initData : "",
    },
  };
  if (typeof window !== "undefined" && window.KFC_DEV_TELEGRAM_ID) {
    opt.headers["X-Dev-Telegram-Id"] = String(window.KFC_DEV_TELEGRAM_ID);
  }
  if (body !== undefined) {
    opt.method = "POST";
    opt.body = JSON.stringify(body);
  }
  const r = await fetch(path, opt);
  let data = {};
  try { data = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error(data.error || `Erreur ${r.status}`);
  return data;
};

const $ = (id) => document.getElementById(id);

const state = {
  menuLoaded: false,
  categories: [],
  currentItem: null,   // { name, modgrps }
  cartCount: 0,
  lastOrder: null,     // { number, uuid, state }
};

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
    state.connected = data.connected;
    renderMenu(data.categories, data.connected);
    refreshCart();
  } catch (e) {
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

function renderMenu(categories, connected) {
  const c = $("menu-container");
  c.innerHTML = "";
  if (!categories.length) {
    c.innerHTML = `<div class="empty-hint">Aucun article fidélité disponible dans ce restaurant.</div>`;
    return;
  }
  categories.forEach((cat) => {
    const title = document.createElement("div");
    title.className = "cat-title";
    title.textContent = cat.name;
    c.appendChild(title);

    const grid = document.createElement("div");
    grid.className = "product-grid";
    cat.items.forEach((it) => {
      const card = document.createElement("div");
      const available = it.available !== false && it.price != null;
      card.className = available ? "product-card" : "product-card unavailable";
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
      const priceHtml = available
        ? `<div class="product-price-row">
             <span class="price-old">${Number(it.originalPrice != null ? it.originalPrice : it.price).toFixed(2)} €</span>
             <span class="price-new">${Number(it.price).toFixed(2)} €</span>
           </div>`
        : `<div class="product-price soon">Bientôt disponible</div>`;
      card.innerHTML = `
        ${thumb}
        <div class="product-info">
          <div class="product-name">${escapeHtml(it.name)}</div>
          ${priceHtml}
        </div>`;
      if (available) {
        card.onclick = () => onItemClick(it);
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
    await api("/api/add-item", { itemId, modgrps });
    toast("Ajouté au panier");
    refreshCart();
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
    state.limit = data.limit || 2500;
    renderCart(data);
  } catch (e) {
    /* silencieux */
  }
}

/* Affiche le solde client (fictif) dans la pastille du header. */
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
          ? (it.originalPrice != null && Number(it.originalPrice) !== Number(it.price)
              ? `<span class="c-price-wrap"><span class="price-old">${Number(it.originalPrice).toFixed(2)}</span><span class="price-new">${Number(it.price).toFixed(2)} ${currency}</span></span>`
              : `<span class="c-pts">${Number(it.price).toFixed(2)} ${currency}</span>`)
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
  toast("Soumission KFC (reCAPTCHA)…");
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
    state: data.status === "SUBMITTED" ? "soumise" : "validée",
  };
  const box = $("confirm-box");
  const url = data.confirmationUrl
    ? `<p class="info-note"><a href="${escapeHtml(data.confirmationUrl)}" target="_blank" rel="noopener">Suivi KFC</a></p>`
    : "";
  box.innerHTML = `
    <p>Commande soumise chez KFC.</p>
    <div class="order-num">N° ${escapeHtml(String(data.orderNumber || "—"))}</div>
    ${url}
    <p class="info-note">Le check-in déclenche la préparation (points débités).</p>
    <button class="primary-btn" id="do-checkin">Je suis là (check-in)</button>
    <button class="secondary-btn" id="back-menu">Retour au menu</button>`;
  $("do-checkin").onclick = doCheckin;
  $("back-menu").onclick = () => {
    // Après soumission le panier KFC est clos : revenir à la recherche.
    backToSearch();
  };
}

async function doCheckin() {
  const btn = $("do-checkin");
  btn.disabled = true;
  toast("Check-in en cours…");
  try {
    const data = await api("/api/checkin", {});
    toast(`Commande confirmée ! N° ${data.orderNumber}`);
    if (state.lastOrder) state.lastOrder.state = "confirmée";
    const url = data.confirmationUrl
      ? `<p class="info-note"><a href="${escapeHtml(data.confirmationUrl)}" target="_blank" rel="noopener">Suivi KFC</a></p>`
      : "";
    $("confirm-box").innerHTML = `
      <p>Check-in OK — commande en préparation.</p>
      <div class="order-num">N° ${escapeHtml(String(data.orderNumber || "—"))}</div>
      ${url}`;
    refreshCart();
  } catch (e) {
    toast(e.message);
    btn.disabled = false;
  }
}

/* ---------- Utilitaires ---------- */
function formatTotal(total) {
  if (total == null) return "—";
  if (typeof total === "number") return total.toFixed(2) + " €";
  return String(total);
}

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

/* Retour à la recherche pour choisir un autre restaurant. */
function backToSearch() {
  state.menuLoaded = false;
  state.categories = [];
  state.connected = undefined;
  state.points = 0;
  const badge = $("cart-badge");
  if (badge) badge.hidden = true;
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
      showScreen("portefeuille");
    } else if (nav === "historique") {
      renderHistory();
      showScreen("historique");
    } else if (nav === "sav") {
      showScreen("sav");
    }
  };
});

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
        const place = [o.storeName, o.storeCity].filter(Boolean).join(" · ");
        const status = o.status || "";
        row.innerHTML = `
          <div class="c-main">
            <div>N° ${escapeHtml(String(o.orderNumber || "—"))}</div>
            <div class="c-opts">${escapeHtml(place)}</div>
          </div>
          <div class="c-right">
            <span class="c-pts">${escapeHtml(pts)}</span>
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
    const cfg = await api("/api/config");
    setBalance(cfg.balance != null ? cfg.balance : 0, cfg.currency || "EUR");
  } catch (e) {
    setBalance(0, "EUR");
  }
  showScreen("search");
  setNav("boutique");
})();
