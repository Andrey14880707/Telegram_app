/* ═══════════════════════════════════════════════════
   MÜNCHEN BARBER — Main Script
   ═══════════════════════════════════════════════════ */

// ── Preloader ────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  const fill = document.getElementById('plFill');
  const pl   = document.getElementById('preloader');
  if (!pl) return;
  if (fill) fill.style.width = '100%';
  setTimeout(() => pl.classList.add('out'), 1200);
});

// ── Custom Cursor ────────────────────────────────────
const cur  = document.getElementById('cursor');
const ring = document.getElementById('cursorRing');
if (cur && ring && window.matchMedia('(hover:hover)').matches) {
  let rx = 0, ry = 0;
  document.addEventListener('mousemove', e => {
    cur.style.left  = e.clientX + 'px';
    cur.style.top   = e.clientY + 'px';
    rx += (e.clientX - rx) * .12;
    ry += (e.clientY - ry) * .12;
    ring.style.left = rx + 'px';
    ring.style.top  = ry + 'px';
  });
  requestAnimationFrame(function loop() {
    ring.style.left = rx + 'px';
    ring.style.top  = ry + 'px';
    requestAnimationFrame(loop);
  });
}

// ── Navbar ───────────────────────────────────────────
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => {
  nav && (window.scrollY > 60 ? nav.classList.add('stuck') : nav.classList.remove('stuck'));
}, { passive: true });

// ── Mobile Menu ──────────────────────────────────────
const burger  = document.getElementById('navBurger');
const mobMenu = document.getElementById('mobMenu');
function closeMob() {
  if (!mobMenu) return;
  mobMenu.classList.remove('open');
  burger && burger.classList.remove('open');
  document.body.style.overflow = '';
}
if (burger) {
  burger.addEventListener('click', () => {
    const isOpen = mobMenu.classList.toggle('open');
    burger.classList.toggle('open', isOpen);
    document.body.style.overflow = isOpen ? 'hidden' : '';
  });
}

// ── Clock ────────────────────────────────────────────
function updateClock() {
  const t = new Date().toLocaleTimeString('de-DE', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    timeZone: 'Europe/Berlin'
  });
  const mob = document.getElementById('heroTime');
  if (mob) mob.textContent = t;
}
updateClock();
setInterval(updateClock, 1000);

// ── Open/Closed status ────────────────────────────────
function checkStatus() {
  const el = document.getElementById('bkStatus');
  if (!el) return;
  const now = new Date(new Date().toLocaleString('en-US', { timeZone: 'Europe/Berlin' }));
  const wd = now.getDay();   // 0=Sun
  const h  = now.getHours() + now.getMinutes() / 60;
  let open = false;
  // Mon(1): closed, Tue-Fri(2-5): 10-20, Sat(6): 9-18, Sun(0): closed
  if (wd >= 2 && wd <= 5) open = h >= 10 && h < 20;
  else if (wd === 6)       open = h >= 9  && h < 18;
  const lang = localStorage.getItem('lang') || 'de';
  const openTxt  = {de:'🟢 Jetzt geöffnet',  ru:'🟢 Сейчас открыто',  uk:'🟢 Зараз відкрито'}[lang]  || '🟢 Jetzt geöffnet';
  const closeTxt = {de:'🔴 Aktuell geschlossen', ru:'🔴 Сейчас закрыто', uk:'🔴 Зараз зачинено'}[lang] || '🔴 Aktuell geschlossen';
  el.className = 'bk-status ' + (open ? 'open' : 'closed');
  el.textContent = open ? openTxt : closeTxt;
}
checkStatus();

// ── Counter animation ─────────────────────────────────
function animateCounter(el) {
  const target = parseInt(el.dataset.target, 10);
  const suffix = el.dataset.suffix || '';
  let current = 0;
  const duration = 1800;
  const step = target / (duration / 16);
  const timer = setInterval(() => {
    current = Math.min(current + step, target);
    el.textContent = Math.floor(current) + suffix;
    if (current >= target) clearInterval(timer);
  }, 16);
}

// ── Scroll reveal ─────────────────────────────────────
const revealObs = new IntersectionObserver((entries) => {
  entries.forEach((entry, i) => {
    if (!entry.isIntersecting) return;
    setTimeout(() => {
      entry.target.classList.add('in');
      // Skills
      entry.target.querySelectorAll('.sbar > div').forEach(bar => {
        bar.style.width = (bar.dataset.w || 0) + '%';
      });
      // Counters
      entry.target.querySelectorAll('.bnum[data-target]').forEach(animateCounter);
    }, i * 100);
    revealObs.unobserve(entry.target);
  });
}, { threshold: .12 });

document.querySelectorAll('.reveal, .reveal-l, .reveal-r').forEach(el => revealObs.observe(el));

// Observe stat numbers separately (they're inside reveal-l)
const numObs = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.querySelectorAll('.bnum[data-target]').forEach(animateCounter);
      numObs.unobserve(entry.target);
    }
  });
}, { threshold: .3 });
document.querySelectorAll('.about-nums').forEach(el => numObs.observe(el));

// ── Work Slider (Premium Snap) ──────────────────────
let _workPhotos = [], _workFiltered = [], _workIdx = 0;
const CAT_LABELS = {Fade:'✂ Fade',Classic:'💈 Classic',Bart:'🪒 Bart',FullLook:'⚡ Full Look',Sonstiges:'📷 Sonstiges'};

(async function initWork() {
  const grid = document.getElementById('workGrid');
  const prev = document.getElementById('workPrev');
  const next = document.getElementById('workNext');
  if (!grid) return;

  try {
    const res  = await fetch('/api/photos');
    const data = await res.json();
    if (data.photos && data.photos.length) {
      _workPhotos = data.photos;
      _workFiltered = data.photos;
      buildWork();
    }
  } catch { /* keep fallbacks */ }

  // Arrows
  prev?.addEventListener('click', () => {
    grid.scrollBy({ left: -grid.offsetWidth * 0.8, behavior: 'smooth' });
  });
  next?.addEventListener('click', () => {
    grid.scrollBy({ left: grid.offsetWidth * 0.8, behavior: 'smooth' });
  });

  // Category pills
  document.querySelectorAll('.wcat').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.wcat').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _workFiltered = btn.dataset.cat === 'all' ? _workPhotos : _workPhotos.filter(p => p.category === btn.dataset.cat);
      buildWork();
    });
  });

  // Track scroll for dots
  grid.addEventListener('scroll', () => {
    const idx = Math.round(grid.scrollLeft / (grid.querySelector('.wc')?.offsetWidth || 1));
    updateWorkDots(idx);
  }, { passive: true });
})();

function buildWork() {
  const grid = document.getElementById('workGrid');
  const dots = document.getElementById('workDots');
  if (!grid) return;

  if (_workFiltered.length) {
    grid.innerHTML = _workFiltered.map((p, i) => `
      <div class="wc" style="--i:${i}">
        <img src="/uploads/${p.filename}" alt="${p.caption || ''}" loading="lazy">
        <div class="wc-bottom">
          <span class="wc-t">${p.category}</span>
          <span class="wc-sub">${p.caption || 'Haircut & Design'}</span>
        </div>
        <a href="#termin" class="wc-overlay">Buchen ↗</a>
      </div>`).join('');
  }

  // Build dots
  if (dots) {
    dots.innerHTML = _workFiltered.map((_, i) => `<div class="w-dot ${i===0?'active':''}" onclick="workTo(${i})"></div>`).join('');
  }
}

function updateWorkDots(idx) {
  document.querySelectorAll('.w-dot').forEach((d, i) => d.classList.toggle('active', i === idx));
}

function workTo(idx) {
  const grid = document.getElementById('workGrid');
  const cards = grid.querySelectorAll('.wc');
  if (cards[idx]) {
    cards[idx].scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
  }
}

// ── Flatpickr date picker ─────────────────────────────
let _disabledDates = [];
async function initDatePicker() {
  const dateInput = document.getElementById('bDate');
  if (!dateInput || typeof flatpickr === 'undefined') return;

  try {
    const res  = await fetch('/api/availability');
    const data = await res.json();
    _disabledDates = data.disabled || [];
  } catch { _disabledDates = []; }

  const today  = new Date();
  const maxDay = new Date(today); maxDay.setDate(today.getDate() + 60);

  flatpickr(dateInput, {
    locale: 'de',
    minDate: today,
    maxDate: maxDay,
    disable: _disabledDates,
    disableMobile: true,
    onChange: ([selectedDate]) => {
      if (selectedDate) loadSlots();
    },
  });
}
initDatePicker();

// ── Time slots (grid) ──────────────────────────────────
async function loadSlots() {
  const date = document.getElementById('bDate').value;
  const grid = document.getElementById('timeGrid');
  const hidden = document.getElementById('bTime');
  if (!date || !grid) return;

  grid.innerHTML = '<div class="tg-loading">Lädt...</div>';
  if (hidden) hidden.value = '';

  try {
    const res  = await fetch(`/api/slots?date=${date}`);
    const data = await res.json();

    grid.innerHTML = '';
    if (data.closed) {
      grid.innerHTML = '<div class="tg-hint">Geschlossen</div>';
      return;
    }
    const available = data.slots || [];
    const booked    = data.booked || [];
    if (!available.length && !booked.length) {
      grid.innerHTML = '<div class="tg-hint">Keine freien Zeiten</div>';
      return;
    }
    // Merge + sort all slots
    const all = [...new Set([...available, ...booked])].sort();
    all.forEach(slot => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'tg-slot' + (booked.includes(slot) ? ' booked' : '');
      btn.textContent = slot;
      if (!booked.includes(slot)) {
        btn.addEventListener('click', () => {
          grid.querySelectorAll('.tg-slot').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          if (hidden) hidden.value = slot;
        });
      }
      grid.appendChild(btn);
    });
  } catch {
    grid.innerHTML = '<div class="tg-hint">Fehler beim Laden</div>';
  }
}

// ── Floating book button ───────────────────────────────
const floatBook = document.getElementById('floatBook');
const heroSection = document.querySelector('.hero');
const bookingSection = document.getElementById('termin');
if (floatBook && heroSection) {
  const updateFloat = () => {
    const heroBottom    = heroSection.getBoundingClientRect().bottom;
    const bookingTop    = bookingSection ? bookingSection.getBoundingClientRect().top : Infinity;
    const wh            = window.innerHeight;
    const pastHero      = heroBottom < 0;
    const atBooking     = bookingTop < wh * 0.8;
    if (pastHero && !atBooking) {
      floatBook.classList.add('visible');
    } else {
      floatBook.classList.remove('visible');
    }
  };
  window.addEventListener('scroll', updateFloat, { passive: true });
  updateFloat();
}

// ── Booking form ──────────────────────────────────────
const bookForm = document.getElementById('bookForm');
if (bookForm) {
  bookForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('submitBtn');
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Wird gesendet...';
    document.querySelector('.form-err')?.remove();

    const payload = {
      name:    document.getElementById('bName').value.trim(),
      phone:   document.getElementById('bPhone').value.trim(),
      email:   document.getElementById('bEmail').value.trim(),
      telegram:document.getElementById('bTelegram').value.trim(),
      service: document.getElementById('bService').value,
      date:    document.getElementById('bDate').value,
      time:    document.getElementById('bTime').value,
      comment: document.getElementById('bComment').value.trim(),
    };

    try {
      const res  = await fetch('/api/book', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.success) {
        document.getElementById('mMsg').textContent = data.message;
        openModal();
        bookForm.reset();
        const grid = document.getElementById('timeGrid');
        if (grid) grid.innerHTML = '<div class="tg-hint">Erst Datum wählen</div>';
      } else {
        showErr(data.error || 'Unbekannter Fehler');
      }
    } catch {
      showErr('Verbindungsfehler — bitte erneut versuchen');
    } finally {
      btn.disabled = false;
      btn.textContent = orig;
    }
  });
}

function showErr(msg) {
  const el = document.createElement('div');
  el.className = 'form-err';
  el.style.cssText = 'color:#ef4444;background:rgba(239,68,68,.08);border-left:2px solid #ef4444;padding:.75rem 1rem;font-size:.82rem;margin-bottom:1rem;';
  el.textContent = '⚠ ' + msg;
  bookForm.insertBefore(el, bookForm.querySelector('[type=submit]'));
}

// ── Modal ──────────────────────────────────────────────
function openModal() {
  document.getElementById('mOverlay').classList.add('on');
  document.getElementById('mBox').classList.add('on');
}
function closeModal() {
  document.getElementById('mOverlay').classList.remove('on');
  document.getElementById('mBox').classList.remove('on');
}

// ── Language Switcher ─────────────────────────────────
const LANGS = {
  de: {
    nav_ueber:'Über mich', nav_services:'Services', nav_preise:'Preise', nav_termin:'Termin',
    hero_tag:'Ich mache deinen Look besser', hero_btn:'Termin buchen',
    stat_kunden:'KUNDEN', stat_exp:'JAHRE ERFAHRUNG',
    about_eyebrow:'01 — ÜBER MICH',
    about_h2:'Professioneller<br><em>Barbier</em><br>in München',
    about_p1:'Spezialist für Fades, klassische Haarschnitte und Bartpflege. Mit über 5 Jahren Erfahrung und einem Auge fürs Detail bringe ich jeden Look auf das nächste Level.',
    about_ig:'Instagram ansehen ↗',
    skill1:'Fades & Skin Fades', skill2:'Klassische Haarschnitte', skill3:'Bartpflege & Rasur',
    work_eyebrow:'UNSERE ARBEIT', work_h2:'Aktuelle<br>Arbeiten',
    work_more:'Mehr auf Instagram ↗', cat_all:'Alle', work_ig_p:'Echte Ergebnisse auf Instagram',
    prices_eyebrow:'03 — PREISLISTE', prices_h2:'Was ich<br>anbiete',
    svc1:'Klassischer Haarschnitt', svc2:'Haarschnitt (Maschine)', svc3:'✦ Fade / Skin Fade',
    svc4:'★ Haarschnitt + Bart', svc5:'Bartpflege', svc6:'Heißrasur',
    svc7:'Kinder (bis 12 J.)', svc8:'Styling', svc9:'Grau-Kaschierung', svc10:'Haarschnitt + Styling',
    prices_note:'* Alle Preise inkl. MwSt.', prices_btn:'Jetzt buchen',
    bk_eyebrow:'TERMIN BUCHEN', bk_h2:'Wann<br>kommst du?',
    bk_desc:'Wähle deinen Wunschtermin — Bestätigung kommt sofort.',
    oh_title:'ÖFFNUNGSZEITEN', oh_mon:'Montag', oh_closed:'Geschlossen',
    oh_di:'Di — Fr', oh_sat:'Samstag', oh_sun:'Sonntag',
    f_name:'Name *', f_phone:'Telefon *', f_reminder:'(Erinnerung)',
    f_service:'Service *', f_service_ph:'Service wählen ...',
    f_svc1:'Klassischer Haarschnitt — 25€', f_svc2:'Haarschnitt (Maschine) — 20€',
    f_svc3:'Fade / Skin Fade — 30€', f_svc4:'★ Haarschnitt + Bart — 40€',
    f_svc5:'Bartpflege — 20€', f_svc6:'Heißrasur — 30€',
    f_svc7:'Kinder (bis 12 J.) — 20€', f_svc8:'Styling — 15€',
    f_svc9:'Grau-Kaschierung — 35€', f_svc10:'Haarschnitt + Styling — 35€',
    f_date:'Datum *', f_time:'Uhrzeit *', f_time_hint:'Erst Datum wählen',
    f_date_ph:'Datum wählen', f_comment_ph:'Besondere Wünsche...',
    f_comment:'Anmerkungen', f_submit:'Termin buchen ✂',
    modal_h3:'Termin bestätigt!', modal_msg:'Bis bald! Bestätigung kommt in Kürze.', modal_btn:'Perfekt!',
    float_btn:'✂ Termin buchen', wc_book:'Buchen ↗', nav_feed:'Feed', feed_all:'Alle Beiträge →',
    feed_title:'Feed', feed_sub:'Neuigkeiten &amp; Arbeiten',
  },
  ru: {
    nav_ueber:'Обо мне', nav_services:'Услуги', nav_preise:'Цены', nav_termin:'Запись',
    hero_tag:'Я делаю твой образ лучше', hero_btn:'Записаться',
    stat_kunden:'КЛИЕНТОВ', stat_exp:'ЛЕТ ОПЫТА',
    about_eyebrow:'01 — ОБО МНЕ',
    about_h2:'Профессиональный<br><em>Барбер</em><br>в Мюнхене',
    about_p1:'Специалист по фейдам, классическим стрижкам и уходу за бородой. Более 5 лет опыта и внимание к деталям — каждый образ на новый уровень.',
    about_ig:'Смотреть Instagram ↗',
    skill1:'Фейды & Скин Фейды', skill2:'Классические стрижки', skill3:'Уход за бородой & бритьё',
    work_eyebrow:'НАШИ РАБОТЫ', work_h2:'Актуальные<br>Работы',
    work_more:'Больше в Instagram ↗', cat_all:'Все', work_ig_p:'Реальные результаты в Instagram',
    prices_eyebrow:'03 — ПРАЙСЛИСТ', prices_h2:'Что я<br>предлагаю',
    svc1:'Классическая стрижка', svc2:'Стрижка машинкой', svc3:'✦ Fade / Skin Fade',
    svc4:'★ Стрижка + Борода', svc5:'Уход за бородой', svc6:'Горячее бритьё',
    svc7:'Дети (до 12 лет)', svc8:'Стайлинг', svc9:'Камуфляж седины', svc10:'Стрижка + Стайлинг',
    prices_note:'* Все цены вкл. НДС.', prices_btn:'Записаться сейчас',
    bk_eyebrow:'ОНЛАЙН ЗАПИСЬ', bk_h2:'Когда<br>придёшь?',
    bk_desc:'Выберите удобное время — подтверждение придёт сразу.',
    oh_title:'ЧАСЫ РАБОТЫ', oh_mon:'Понедельник', oh_closed:'Закрыто',
    oh_di:'Вт — Пт', oh_sat:'Суббота', oh_sun:'Воскресенье',
    f_name:'Имя *', f_phone:'Телефон *', f_reminder:'(напоминание)',
    f_service:'Услуга *', f_service_ph:'Выберите услугу ...',
    f_svc1:'Классическая стрижка — 25€', f_svc2:'Стрижка машинкой — 20€',
    f_svc3:'Fade / Skin Fade — 30€', f_svc4:'★ Стрижка + Борода — 40€',
    f_svc5:'Уход за бородой — 20€', f_svc6:'Горячее бритьё — 30€',
    f_svc7:'Дети (до 12 лет) — 20€', f_svc8:'Стайлинг — 15€',
    f_svc9:'Камуфляж седины — 35€', f_svc10:'Стрижка + Стайлинг — 35€',
    f_date:'Дата *', f_time:'Время *', f_time_hint:'Сначала дату',
    f_date_ph:'Выбрать дату', f_comment_ph:'Особые пожелания...',
    f_comment:'Примечания', f_submit:'Записаться ✂',
    modal_h3:'Запись подтверждена!', modal_msg:'До скорого! Подтверждение придёт в ближайшее время.', modal_btn:'Отлично!',
    float_btn:'✂ Записаться', wc_book:'Записаться ↗', nav_feed:'Лента', feed_all:'Вся лента →',
    feed_title:'Лента', feed_sub:'Новости &amp; Работы барбершопа',
  },
  uk: {
    nav_ueber:'Про мене', nav_services:'Послуги', nav_preise:'Ціни', nav_termin:'Запис',
    hero_tag:'Я роблю твій образ кращим', hero_btn:'Записатися',
    stat_kunden:'КЛІЄНТІВ', stat_exp:'РОКІВ ДОСВІДУ',
    about_eyebrow:'01 — ПРО МЕНЕ',
    about_h2:'Професійний<br><em>Барбер</em><br>у Мюнхені',
    about_p1:'Спеціаліст з фейдів, класичних стрижок та догляду за бородою. Понад 5 років досвіду та увага до деталей — кожен образ на новий рівень.',
    about_ig:'Дивитися Instagram ↗',
    skill1:'Фейди & Скін Фейди', skill2:'Класичні стрижки', skill3:'Догляд за бородою & гоління',
    work_eyebrow:'НАШІ РОБОТИ', work_h2:'Актуальні<br>Роботи',
    work_more:'Більше в Instagram ↗', cat_all:'Всі', work_ig_p:'Реальні результати в Instagram',
    prices_eyebrow:'03 — ПРАЙСЛІСТ', prices_h2:'Що я<br>пропоную',
    svc1:'Класична стрижка', svc2:'Стрижка машинкою', svc3:'✦ Fade / Skin Fade',
    svc4:'★ Стрижка + Борода', svc5:'Догляд за бородою', svc6:'Гаряче гоління',
    svc7:'Діти (до 12 р.)', svc8:'Стайлінг', svc9:'Камуфляж сивини', svc10:'Стрижка + Стайлінг',
    prices_note:'* Всі ціни вкл. ПДВ.', prices_btn:'Записатися зараз',
    bk_eyebrow:'ОНЛАЙН ЗАПИС', bk_h2:'Коли<br>прийдеш?',
    bk_desc:'Оберіть зручний час — підтвердження надійде одразу.',
    oh_title:'ГОДИНИ РОБОТИ', oh_mon:'Понеділок', oh_closed:'Зачинено',
    oh_di:'Вт — Пт', oh_sat:'Субота', oh_sun:'Неділя',
    f_name:"Ім'я *", f_phone:'Телефон *', f_reminder:'(нагадування)',
    f_service:'Послуга *', f_service_ph:'Оберіть послугу ...',
    f_svc1:'Класична стрижка — 25€', f_svc2:'Стрижка машинкою — 20€',
    f_svc3:'Fade / Skin Fade — 30€', f_svc4:'★ Стрижка + Борода — 40€',
    f_svc5:'Догляд за бородою — 20€', f_svc6:'Гаряче гоління — 30€',
    f_svc7:'Діти (до 12 р.) — 20€', f_svc8:'Стайлінг — 15€',
    f_svc9:'Камуфляж сивини — 35€', f_svc10:'Стрижка + Стайлінг — 35€',
    f_date:'Дата *', f_time:'Час *', f_time_hint:'Спочатку дату',
    f_date_ph:'Обрати дату', f_comment_ph:'Особливі побажання...',
    f_comment:'Примітки', f_submit:'Записатися ✂',
    modal_h3:'Запис підтверджено!', modal_msg:'До зустрічі! Підтвердження надійде незабаром.', modal_btn:'Чудово!',
    float_btn:'✂ Записатися', wc_book:'Записатися ↗', nav_feed:'Стрічка', feed_all:'Уся стрічка →',
    feed_title:'Стрічка', feed_sub:'Новини &amp; Роботи барбершопу',
  }
};

function setLang(lang) {
  if (!LANGS[lang]) return;
  const L = LANGS[lang];
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (L[key] !== undefined) el.innerHTML = L[key];
  });
  document.querySelectorAll('[data-i18n-ph]').forEach(el => {
    const key = el.dataset.i18nPh;
    if (L[key] !== undefined) el.placeholder = L[key];
  });
  document.querySelectorAll('.lang-sw button').forEach(b =>
    b.classList.toggle('active', b.dataset.lang === lang)
  );
  document.documentElement.lang = lang;
  localStorage.setItem('lang', lang);
}

document.querySelectorAll('.lang-sw button').forEach(b =>
  b.addEventListener('click', () => setLang(b.dataset.lang))
);
setLang(localStorage.getItem('lang') || 'de');

// ── Premium Animations ────────────────────────────────

// 1. Scroll progress bar
(function initScrollProgress() {
  const bar = document.createElement('div');
  bar.className = 'scroll-progress';
  document.body.prepend(bar);
  window.addEventListener('scroll', () => {
    const pct = window.scrollY / (document.body.scrollHeight - window.innerHeight) * 100;
    bar.style.width = Math.min(pct, 100) + '%';
  }, { passive: true });
})();

// 2. Counter animation for stat numbers
function animateCounter(el) {
  const target = parseFloat(el.dataset.target || el.textContent);
  const suffix = el.dataset.suffix || '';
  const duration = 1600;
  const start = performance.now();
  const isFloat = String(target).includes('.');
  function step(now) {
    const p = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - p, 4);
    const val = target * ease;
    el.textContent = (isFloat ? val.toFixed(1) : Math.floor(val)) + suffix;
    if (p < 1) requestAnimationFrame(step);
    else el.textContent = target + suffix;
  }
  requestAnimationFrame(step);
}

// 3. Intersection observer — reveal + stagger + counters
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    const el = entry.target;
    el.classList.add('in');
    if (el.classList.contains('count-up')) animateCounter(el);
    observer.unobserve(el);
  });
}, { threshold: 0.15 });

document.querySelectorAll('.reveal, .reveal-l, .reveal-r, .stagger-children, .count-up').forEach(el => observer.observe(el));

// 4. Card tilt on desktop (also applies to .wc, .hours-card, .pr-card dynamically)
if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
  document.querySelectorAll('.tilt-card, .wc, .hours-card').forEach(card => {
    card.addEventListener('mousemove', e => {
      const r = card.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width  - 0.5;
      const y = (e.clientY - r.top)  / r.height - 0.5;
      card.style.transform = `perspective(600px) rotateY(${x * 8}deg) rotateX(${-y * 8}deg) scale(1.02)`;
    });
    card.addEventListener('mouseleave', () => {
      card.style.transform = '';
    });
  });
}

// 5. Magnetic buttons (subtle follow on hover)
if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
  document.querySelectorAll('.btn-primary, .btn-outline').forEach(btn => {
    btn.addEventListener('mousemove', e => {
      const r = btn.getBoundingClientRect();
      const x = (e.clientX - r.left - r.width  / 2) * 0.25;
      const y = (e.clientY - r.top  - r.height / 2) * 0.25;
      btn.style.transform = `translate(${x}px, ${y}px)`;
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.transform = '';
      btn.style.transition = 'transform .4s cubic-bezier(.16,1,.3,1)';
      setTimeout(() => btn.style.transition = '', 400);
    });
  });
}

// 6. Hero parallax on scroll
(function initParallax() {
  const hero = document.querySelector('.hero');
  const bg   = document.querySelector('.bg-pattern');
  if (!hero || !bg) return;
  window.addEventListener('scroll', () => {
    const y = window.scrollY;
    if (y > window.innerHeight) return;
    bg.style.transform = `translateY(${y * 0.3}px)`;
  }, { passive: true });
})();
