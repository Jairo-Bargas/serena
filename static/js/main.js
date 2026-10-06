/* Serena Nails · interacciones y animaciones */
(() => {
  const root = document.documentElement;
  const $ = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => [...c.querySelectorAll(s)];
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const desktop = matchMedia("(min-width: 960px)");
  const hasGsap = !!(window.gsap && window.ScrollTrigger);
  const motion = hasGsap && !reduce;
  if (!motion) root.classList.add("no-motion");

  /* ------------------------------------------------ smooth scroll */
  let lenis = null;
  if (motion && window.Lenis) {
    lenis = new Lenis({ duration: 1.15, smoothWheel: true });
    lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add((t) => lenis.raf(t * 1000));
    gsap.ticker.lagSmoothing(0);
  }
  const scrollTo = (target) => {
    if (lenis) lenis.scrollTo(target, { offset: -60 });
    else target.scrollIntoView({ behavior: reduce ? "auto" : "smooth" });
  };
  $$('a[href*="#"]').forEach((a) => {
    a.addEventListener("click", (e) => {
      const url = new URL(a.href, location.href);
      if (url.pathname !== location.pathname || !url.hash) return;
      const target = document.getElementById(url.hash.slice(1));
      if (!target) return;
      e.preventDefault();
      closeMenu();
      scrollTo(target);
      history.replaceState(null, "", url.hash);
    });
  });

  /* ------------------------------------------------ nav + menú + dock */
  const nav = $("[data-nav]");
  const dock = $("[data-dock]");
  const hero = $("[data-hero]");
  let lastY = 0;
  const onScroll = () => {
    const y = window.scrollY;
    const heroH = hero ? hero.offsetHeight : 0;
    if (nav) {
      nav.classList.toggle("is-solid", y > (hero ? heroH - 90 : 10));
      const menuOpen = document.body.classList.contains("menu-open");
      nav.classList.toggle("is-hidden", !menuOpen && y > lastY + 4 && y > 400);
      if (y < lastY - 4) nav.classList.remove("is-hidden");
    }
    if (dock) dock.classList.toggle("is-visible", y > (hero ? heroH * 0.6 : 200));
    lastY = y;
  };
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  const menuBtn = $("[data-menu-toggle]");
  const menu = $("[data-menu]");
  function closeMenu() {
    if (!document.body.classList.contains("menu-open")) return;
    document.body.classList.remove("menu-open");
    menuBtn?.setAttribute("aria-expanded", "false");
    menu?.setAttribute("aria-hidden", "true");
    lenis?.start();
  }
  menuBtn?.addEventListener("click", () => {
    const open = !document.body.classList.contains("menu-open");
    if (!open) return closeMenu();
    document.body.classList.add("menu-open");
    menuBtn.setAttribute("aria-expanded", "true");
    menu.setAttribute("aria-hidden", "false");
    nav.classList.remove("is-hidden");
    lenis?.stop();
  });
  addEventListener("keydown", (e) => { if (e.key === "Escape") { closeMenu(); closeLightbox(); } });

  /* ------------------------------------------------ preloader + intro del hero */
  const pre = $("[data-preloader]");
  const heroIntro = () => {
    if (!motion || !hero) return;
    gsap.fromTo("[data-hero-item]",
      { y: 40, opacity: 0, filter: "blur(8px)" },
      { y: 0, opacity: 1, filter: "blur(0px)", duration: 1.4, ease: "expo.out", stagger: 0.12, clearProps: "filter" });
    gsap.from("[data-hero-media]", { scale: 1.15, duration: 2.4, ease: "expo.out" });
  };
  if (pre) {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      pre.classList.add("is-done");
      setTimeout(heroIntro, 250);
      setTimeout(() => pre.remove(), 1400);
    };
    if (document.readyState === "complete") setTimeout(finish, 700);
    else addEventListener("load", () => setTimeout(finish, 500));
    setTimeout(finish, 2600);
    if (motion) gsap.set("[data-hero-item]", { opacity: 0 });
  }

  /* ------------------------------------------------ slideshow del hero */
  const slides = $$(".slide");
  const dotsWrap = $("[data-slide-dots]");
  if (slides.length > 1) {
    let i = 0;
    const dots = slides.map(() => { const d = document.createElement("span"); dotsWrap?.appendChild(d); return d; });
    const show = (n) => {
      slides[i].classList.remove("is-active"); dots[i].classList.remove("is-active");
      i = n % slides.length;
      slides[i].classList.add("is-active");
      void dots[i].offsetWidth; dots[i].classList.add("is-active");
    };
    dots[0].classList.add("is-active");
    if (!reduce) setInterval(() => !document.hidden && show(i + 1), 6000);
  }

  /* ------------------------------------------------ tabs de servicios */
  const tabs = $("[data-tabs]");
  if (tabs) {
    const buttons = $$("[data-tab]", tabs);
    tabs.dataset.active = buttons[0].dataset.tab;
    const select = (btn) => {
      buttons.forEach((b) => {
        const on = b === btn;
        b.setAttribute("aria-selected", on); b.tabIndex = on ? 0 : -1;
        const panel = $(`[data-panel="${b.dataset.tab}"]`);
        panel.hidden = !on; panel.classList.toggle("is-active", on);
      });
      tabs.dataset.active = btn.dataset.tab;
      if (motion) ScrollTrigger.refresh();
      countUp($$(`[data-panel="${btn.dataset.tab}"] [data-count]`));
    };
    buttons.forEach((b, idx) => {
      b.addEventListener("click", () => select(b));
      b.addEventListener("keydown", (e) => {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        const next = buttons[(idx + (e.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length];
        next.focus(); select(next);
      });
    });
  }

  /* spotlight + tilt en cards */
  if (matchMedia("(hover: hover)").matches) {
    $$("[data-tilt]").forEach((card) => {
      card.addEventListener("pointermove", (e) => {
        const r = card.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        card.style.setProperty("--mx", `${x * 100}%`);
        card.style.setProperty("--my", `${y * 100}%`);
        if (!reduce) card.style.transform = `perspective(900px) rotateX(${(0.5 - y) * 4}deg) rotateY(${(x - 0.5) * 5}deg) translateY(-4px)`;
      });
      card.addEventListener("pointerleave", () => { card.style.transform = ""; });
    });
  }

  /* ------------------------------------------------ precios: bajan hasta el valor real (900 arranca en 1.000) */
  const money = (v) => "$" + Math.round(v).toLocaleString("es-UY");
  const priceFrom = (end) => Math.ceil(end / 100) * 100 + 100;
  if (motion) $$("[data-count]").forEach((el) => { el.textContent = money(priceFrom(+el.dataset.count)); });
  function countUp(els) {
    if (!motion) return;
    els.forEach((el) => {
      const end = +el.dataset.count;
      const obj = { v: priceFrom(end) };
      el.textContent = money(obj.v);
      gsap.to(obj, {
        v: end, duration: 1.8, delay: 0.35, ease: "power3.inOut",
        onUpdate: () => { el.textContent = money(obj.v); },
      });
    });
  }

  /* ------------------------------------------------ reel del espacio */
  const reel = $("[data-reel]");
  if (reel) {
    const items = $$("[data-reel-item]", reel);
    const bars = $("[data-reel-bars]", reel);
    const spans = items.map(() => { const s = document.createElement("span"); s.innerHTML = "<i></i>"; bars.appendChild(s); return s; });
    let i = 0, timer = null, tween = null, running = false;
    const play = (n) => {
      items[i].classList.remove("is-active");
      if (items[i].tagName === "VIDEO") items[i].pause();
      spans.forEach((s, k) => { s.classList.toggle("is-done", k < n); s.firstChild.style.transform = k < n ? "scaleX(1)" : "scaleX(0)"; });
      i = n;
      const el = items[i];
      el.classList.add("is-active");
      const bar = spans[i].firstChild;
      const next = () => play((i + 1) % items.length);
      clearTimeout(timer); tween?.kill?.();
      if (el.tagName === "VIDEO") {
        el.currentTime = 0; el.play().catch(() => {});
        el.onended = next;
        el.ontimeupdate = () => { if (el.duration) bar.style.transform = `scaleX(${el.currentTime / el.duration})`; };
        if (!el.duration) timer = setTimeout(next, 9000);
      } else {
        const ms = 4200;
        if (motion) tween = gsap.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: ms / 1000, ease: "none" });
        else bar.style.transform = "scaleX(1)";
        timer = setTimeout(next, ms);
      }
    };
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !running) { running = true; play(i); }
      else if (!e.isIntersecting && running) {
        running = false; clearTimeout(timer); tween?.kill?.();
        if (items[i].tagName === "VIDEO") items[i].pause();
      }
    }, { threshold: 0.3 });
    if (!reduce) io.observe(reel);
  }

  /* ------------------------------------------------ giftcard flip */
  const flip = $("[data-flip]");
  if (flip) {
    flip.addEventListener("click", () => flip.classList.toggle("is-flipped"));
    if (!reduce) {
      const auto = setInterval(() => flip.classList.toggle("is-flipped"), 4500);
      flip.addEventListener("click", () => clearInterval(auto), { once: true });
    }
  }

  /* ------------------------------------------------ lightbox */
  const lb = $("[data-lightbox-root]");
  const lbImg = $("[data-lightbox-img]");
  let lbReturn = null;
  $$("[data-lightbox]").forEach((btn) => btn.addEventListener("click", () => {
    lbReturn = btn;
    lbImg.src = btn.dataset.lightbox;
    lbImg.alt = btn.querySelector("img")?.alt || "";
    lb.hidden = false; lenis?.stop();
    $("[data-lightbox-close]", lb).focus();
  }));
  function closeLightbox() {
    if (!lb || lb.hidden) return;
    lb.hidden = true; lenis?.start(); lbReturn?.focus();
  }
  lb?.addEventListener("click", (e) => { if (e.target === lb || e.target.closest("[data-lightbox-close]")) closeLightbox(); });

  /* ------------------------------------------------ Calendly como popup */
  $$("[data-calendly]").forEach((a) => a.addEventListener("click", (e) => {
    if (!window.Calendly) return;
    e.preventDefault();
    Calendly.initPopupWidget({ url: a.dataset.calendly + "?hide_gdpr_banner=1&primary_color=4a342a" });
    window.gtag?.("event", "reservar_click", { servicio: a.dataset.calendly.split("/").pop() });
  }));

  /* ------------------------------------------------ toasts */
  $$(".toast").forEach((t) => setTimeout(() => t.remove(), 5200));

  /* ------------------------------------------------ copiar / compartir (tarjeta) */
  $$("[data-share]").forEach((btn) => btn.addEventListener("click", async () => {
    const data = { title: btn.dataset.shareTitle || document.title, url: btn.dataset.share };
    try {
      if (navigator.share) await navigator.share(data);
      else { await navigator.clipboard.writeText(data.url); btn.dataset.done = "1"; btn.querySelector("span").textContent = "¡Link copiado!"; }
    } catch (_) { /* cancelado */ }
  }));

  /* ------------------------------------------------ tarjeta: sellos animados */
  const fillStamps = (card, upTo, opts = {}) => {
    const stamps = $$(".stamp", card);
    stamps.forEach((s) => s.classList.remove("is-on"));
    stamps.slice(0, upTo).forEach((s, k) => setTimeout(() => s.classList.add("is-on"), (opts.delay || 0) + k * (opts.step || 160)));
  };
  $$("[data-lcard]").forEach((card) => {
    const target = +card.dataset.stamps;
    if (card.classList.contains("lcard--demo")) return;
    if (reduce) return;
    fillStamps(card, target, { delay: 500, step: 140 });
  });

  if (!motion) {
    $$("[data-lcard].lcard--demo").forEach((c) => fillStamps(c, 5));
    return;
  }

  /* ============================================================ GSAP */
  gsap.registerPlugin(ScrollTrigger);

  // títulos: palabras que suben
  $$("[data-split]").forEach((el) => {
    const walk = (node) => {
      [...node.childNodes].forEach((n) => {
        if (n.nodeType === 3) {
          const frag = document.createDocumentFragment();
          n.textContent.split(/(\s+)/).forEach((w) => {
            if (!w) return;
            if (/^\s+$/.test(w)) { frag.append(" "); return; }
            const outer = document.createElement("span"); outer.className = "split-line"; outer.style.display = "inline-block";
            const inner = document.createElement("span"); inner.textContent = w;
            outer.append(inner); frag.append(outer);
          });
          n.replaceWith(frag);
        } else if (n.nodeType === 1) walk(n);
      });
    };
    walk(el);
    gsap.from($$(".split-line > span", el), {
      yPercent: 110, rotate: 4, duration: 1.2, ease: "expo.out", stagger: 0.05,
      scrollTrigger: { trigger: el, start: "top 85%" },
    });
  });

  // apariciones
  $$("[data-reveal]").forEach((el) => gsap.to(el, {
    opacity: 1, y: 0, duration: 1.2, ease: "expo.out",
    scrollTrigger: { trigger: el, start: "top 88%" },
  }));
  $$("[data-stagger]").forEach((el) => gsap.to(el.children, {
    opacity: 1, y: 0, duration: 1.1, ease: "expo.out", stagger: 0.1,
    scrollTrigger: { trigger: el, start: "top 85%" },
  }));
  $$("[data-reveal-img]").forEach((el) => gsap.to(el, {
    clipPath: "inset(0% 0% 0% 0% round 32px)", opacity: 1, duration: 1.6, ease: "expo.out",
    scrollTrigger: { trigger: el, start: "top 85%" },
    onComplete: () => { el.style.clipPath = "none"; },
  }));

  // parallax
  $$("[data-parallax]").forEach((el) => gsap.fromTo(el, { yPercent: 0 }, {
    yPercent: +el.dataset.parallax, ease: "none",
    scrollTrigger: { trigger: el.parentElement, start: "top bottom", end: "bottom top", scrub: true },
  }));
  $$("[data-float]").forEach((el) => gsap.to(el, { y: -14, duration: 2.6, ease: "sine.inOut", yoyo: true, repeat: -1 }));

  // hero se aleja al scrollear
  if (hero) {
    gsap.to(".hero__content", {
      yPercent: 18, opacity: 0, ease: "none",
      scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: true },
    });
    gsap.to("[data-hero-media]", {
      scale: 1.12, ease: "none",
      scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: true },
    });
  }

  // frase que se ilumina palabra por palabra
  $$("[data-words]").forEach((el) => {
    const walk = (node) => [...node.childNodes].forEach((n) => {
      if (n.nodeType === 3) {
        const frag = document.createDocumentFragment();
        n.textContent.split(/(\s+)/).forEach((w) => {
          if (!w.trim()) { frag.append(w); return; }
          const s = document.createElement("span"); s.className = "w"; s.textContent = w; frag.append(s);
        });
        n.replaceWith(frag);
      } else if (n.nodeType === 1) walk(n);
    });
    walk(el);
    const words = $$(".w", el);
    ScrollTrigger.create({
      trigger: el, start: "top 80%", end: "bottom 45%", scrub: true,
      onUpdate: (st) => {
        const n = Math.round(st.progress * words.length);
        words.forEach((w, k) => w.classList.toggle("is-on", k < n));
      },
    });
  });

  // precios
  const visiblePrices = $$(".service-list.is-active [data-count]");
  if (visiblePrices.length) ScrollTrigger.create({ trigger: visiblePrices[0], start: "top 90%", once: true, onEnter: () => countUp(visiblePrices) });

  // galería: scroll horizontal fijado en desktop, barra de progreso en móvil
  const works = $("[data-works]");
  if (works) {
    const track = $("[data-works-track]", works);
    const vp = $("[data-works-viewport]", works);
    const bar = $("[data-works-progress]", works);
    ScrollTrigger.matchMedia({
      "(min-width: 960px)": () => {
        works.classList.add("is-pinned");
        const dist = () => Math.max(0, track.scrollWidth - innerWidth);
        const tw = gsap.to(track, {
          x: () => -dist(), ease: "none",
          scrollTrigger: {
            trigger: works, start: "top top", end: () => "+=" + dist(), pin: true, scrub: 1, invalidateOnRefresh: true,
            onUpdate: (st) => gsap.set(bar, { scaleX: st.progress }),
          },
        });
        return () => { works.classList.remove("is-pinned"); tw.scrollTrigger?.kill(); tw.kill(); gsap.set(track, { x: 0 }); };
      },
      "(max-width: 959px)": () => {
        const upd = () => gsap.set(bar, { scaleX: vp.scrollLeft / Math.max(1, vp.scrollWidth - vp.clientWidth) });
        vp.addEventListener("scroll", upd, { passive: true });
        upd();
        return () => vp.removeEventListener("scroll", upd);
      },
    });
  }

  // tarjeta demo del club: se llena al verla
  const demo = $("[data-club-card] .lcard");
  if (demo) {
    gsap.from(demo, {
      rotateX: 25, rotateY: -20, y: 80, opacity: 0, duration: 1.6, ease: "expo.out",
      scrollTrigger: { trigger: demo, start: "top 85%" },
    });
    let cycle = null;
    // 2 de regalo → hasta el 5 (25%) → hasta el 10 (50%)
    const run = () => {
      const stamps = $$(".stamp", demo);
      stamps.forEach((s) => s.classList.remove("is-on"));
      stamps.forEach((s, k) => {
        const t = k < 2 ? 300 + k * 180 : k < 5 ? 1300 + (k - 2) * 260 : 2700 + (k - 5) * 220;
        setTimeout(() => s.classList.add("is-on"), t);
      });
    };
    ScrollTrigger.create({
      trigger: demo, start: "top 75%", end: "bottom top",
      onEnter: () => { run(); cycle = setInterval(run, 6000); },
      onEnterBack: () => { run(); clearInterval(cycle); cycle = setInterval(run, 6000); },
      onLeave: () => clearInterval(cycle),
      onLeaveBack: () => clearInterval(cycle),
    });
    if (matchMedia("(hover: hover)").matches) {
      const wrap = demo.parentElement;
      wrap.addEventListener("pointermove", (e) => {
        const r = wrap.getBoundingClientRect();
        gsap.to(demo, { rotateY: ((e.clientX - r.left) / r.width - 0.5) * 18, rotateX: (0.5 - (e.clientY - r.top) / r.height) * 14, duration: 0.6, ease: "power2.out" });
      });
      wrap.addEventListener("pointerleave", () => gsap.to(demo, { rotateX: 0, rotateY: 0, duration: 1, ease: "expo.out" }));
    }
  }

  // FAQ: abrir con animación de altura
  $$(".qa").forEach((d) => {
    const s = $("summary", d), body = $(".qa__body", d);
    s.addEventListener("click", (e) => {
      e.preventDefault();
      if (d.open) {
        gsap.to(body, { height: 0, duration: 0.5, ease: "expo.out", onComplete: () => { d.open = false; body.style.height = ""; ScrollTrigger.refresh(); } });
      } else {
        d.open = true;
        gsap.from(body, { height: 0, duration: 0.7, ease: "expo.out", onComplete: () => ScrollTrigger.refresh() });
      }
    });
  });

  addEventListener("load", () => ScrollTrigger.refresh());
})();
