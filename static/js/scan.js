/* Panel Serena · escáner de tarjetas: escanear = sumar sello */
(() => {
  const root = document.querySelector("[data-scan]");
  if (!root) return;
  const csrf = root.dataset.csrf;
  const api = root.dataset.api;
  const visitApi = (id) => root.dataset.visitApi.replace(/0$/, id);
  const msg = root.querySelector("[data-scan-msg]");
  const sheet = root.querySelector("[data-sheet]");
  const body = root.querySelector("[data-sheet-body]");
  const tpl = (name) => document.querySelector(`[data-tpl-${name}]`).content.cloneNode(true);
  let scanner = null, busy = false, lastToken = null, current = null;

  const post = async (url, data) => {
    const r = await fetch(url, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF": csrf },
      body: JSON.stringify(data),
    });
    let json = null;
    try { json = await r.json(); } catch (_) { /* sesión vencida → HTML */ }
    if (!json) throw new Error("Tu sesión venció. Volvé a ingresar al panel.");
    return { status: r.status, json };
  };

  const tokenFrom = (text) => {
    try {
      const u = new URL(text, location.origin);
      const m = u.pathname.match(/\/tarjeta\/([^/?#]+)/);
      return m ? m[1] : null;
    } catch (_) { return null; }
  };

  const openSheet = (frag) => {
    body.replaceChildren(frag);
    sheet.hidden = false;
    setTimeout(() => sheet.classList.add("is-open"), 20);
  };
  const closeSheet = () => {
    sheet.classList.remove("is-open");
    setTimeout(() => { sheet.hidden = true; body.replaceChildren(); }, 350);
    busy = false; current = null;
    setTimeout(() => { lastToken = null; }, 2500);
    try { scanner?.resume(); } catch (_) {}
  };

  const showResult = (c) => {
    const f = tpl("result");
    const $ = (k) => f.querySelector(`[data-f="${k}"]`);
    $("initial").textContent = c.first_name.charAt(0).toUpperCase();
    $("name").textContent = c.name;
    $("stamp").textContent = c.visit.stamp;
    $("card").href = c.card_url;
    const dots = $("dots");
    for (let n = 1; n <= c.total; n++) {
      const li = document.createElement("li");
      if (n < c.visit.stamp) li.className = "on";
      if (n === c.visit.stamp) li.className = "on new";
      dots.append(li);
    }
    if (c.visit.discount) {
      const r = $("reward");
      r.hidden = false;
      r.innerHTML = `<small>Este servicio lleva</small><strong>${c.visit.discount}% OFF</strong>`;
      navigator.vibrate?.([80, 60, 80, 60, 160]);
    } else {
      navigator.vibrate?.(90);
    }
    const left = c.next_reward ? c.next_reward.stamp - c.stamps : null;
    $("next").textContent = c.visit.stamp >= c.total
      ? "¡Completó la tarjeta! Arranca una nueva."
      : left === 1 ? `¡En su próxima visita tiene ${c.next_reward.pct}% OFF!`
      : left ? `Le faltan ${left} para el ${c.next_reward.pct}% OFF.` : "";
    // ojo: guardar las referencias antes de openSheet (después el fragmento queda vacío)
    const chips = $("chips");
    const label = f.querySelector(".res__label");
    chips.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-service]");
      if (!b || chips.dataset.saving) return;
      chips.dataset.saving = "1";
      chips.querySelectorAll(".chip-s").forEach((x) => x.classList.toggle("is-on", x === b));
      navigator.vibrate?.(30);
      try {
        const { json } = await post(visitApi(c.visit.id), { service: b.dataset.service });
        if (!json.ok) throw new Error();
        label.innerHTML = `<span class="res__saved">✓ Guardado: ${b.dataset.service}</span>`;
        setTimeout(closeSheet, 1100);  // vuelve sola al escáner
      } catch (_) {
        delete chips.dataset.saving;
        label.textContent = "No se pudo guardar el servicio. Tocá de nuevo.";
      }
    });
    openSheet(f);
  };

  const showError = (text) => {
    const f = tpl("error");
    f.querySelector('[data-f="msg"]').textContent = text;
    navigator.vibrate?.([40, 40, 40]);
    openSheet(f);
  };

  const addStamp = async (token, force = false) => {
    busy = true;
    try { scanner?.pause(true); } catch (_) {}
    try {
      const { status, json } = await post(api, { token, force });
      if (status === 409 && json.confirm) {
        const f = tpl("confirm");
        f.querySelector('[data-f="name"]').textContent = json.client.name;
        const m = json.minutes;
        f.querySelector('[data-f="minutes"]').textContent = m < 1 ? "menos de un minuto" : m === 1 ? "1 minuto" : `${m} minutos`;
        current = { token };
        openSheet(f);
      } else if (json.ok) {
        current = json.client;
        showResult(json.client);
      } else {
        showError(json.error || "No se pudo sumar el sello.");
      }
    } catch (err) {
      showError(err.message || "Sin conexión. Probá de nuevo.");
    }
  };

  body.addEventListener("click", async (e) => {
    const act = e.target.closest("[data-act]")?.dataset.act;
    if (!act) return;
    if (act === "again") closeSheet();
    if (act === "force" && current?.token) { const t = current.token; body.replaceChildren(); await addStamp(t, true); }
    if (act === "undo" && current?.visit) {
      if (!confirm(`¿Deshacer el sello ${current.visit.stamp} de ${current.first_name}?`)) return;
      try { await post(visitApi(current.visit.id), { undo: true }); } catch (_) {}
      closeSheet();
      msg.textContent = "Sello deshecho.";
    }
  });

  const onScan = (text) => {
    if (busy) return;
    const token = tokenFrom(text);
    if (!token) { if (lastToken !== text) { lastToken = text; showError("Ese QR no es de una tarjeta del Club Serena."); } return; }
    if (token === lastToken) return;
    lastToken = token;
    addStamp(token);
  };

  const start = async () => {
    if (!window.Html5Qrcode) { msg.textContent = "No se pudo cargar el escáner. Revisá la conexión."; return; }
    scanner = new Html5Qrcode("reader", { verbose: false });
    try {
      await scanner.start(
        { facingMode: "environment" },
        { fps: 12, qrbox: (w, h) => { const s = Math.floor(Math.min(w, h) * 0.72); return { width: s, height: s }; }, aspectRatio: 1 },
        onScan, () => {},
      );
      msg.textContent = "";
      root.classList.add("is-live");
    } catch (err) {
      msg.innerHTML = "No pude abrir la cámara.<br>Dale permiso al navegador para usarla y recargá la página.";
    }
  };
  window.serenaScan = onScan; // permite probar sin cámara desde la consola
  start();

  document.addEventListener("visibilitychange", () => {
    if (!scanner) return;
    try { document.hidden ? scanner.pause(true) : (!busy && scanner.resume()); } catch (_) {}
  });
})();
