/* ════════════════════════════════════════════════
   München Barber — Public Site Script
   ════════════════════════════════════════════════ */

// ── Preloader ─────────────────────────────────────
(function(){
  const fill = document.getElementById('plFill');
  const pl   = document.getElementById('preloader');
  let v = 0;
  const iv = setInterval(() => {
    v += Math.random() * 18 + 6;
    if (v >= 100) { v = 100; clearInterval(iv); }
    fill.style.width = v + '%';
  }, 120);
  window.addEventListener('load', () => {
    fill.style.width = '100%';
    setTimeout(() => pl.classList.add('done'), 400);
  });
})();

// ── Cursor ────────────────────────────────────────
(function(){
  const c  = document.getElementById('cursor');
  const cr = document.getElementById('cursorRing');
  if (!c || !cr) return;
  let mx=0,my=0,rx=0,ry=0;
  document.addEventListener('mousemove', e => { mx=e.clientX; my=e.clientY; });
  function loop(){
    c.style.left  = mx+'px'; c.style.top  = my+'px';
    rx += (mx-rx)*.12; ry += (my-ry)*.12;
    cr.style.left = rx+'px'; cr.style.top = ry+'px';
    requestAnimationFrame(loop);
  }
  loop();
})();

// ── Navbar scroll ─────────────────────────────────
(function(){
  const nav = document.getElementById('navbar');
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 40);
  }, {passive:true});
})();

// ── Mobile menu ───────────────────────────────────
(function(){
  const burger = document.getElementById('navBurger');
  const mobile = document.getElementById('navMobile');
  const close  = document.getElementById('navClose');
  if (!burger) return;
  burger.addEventListener('click', () => mobile.classList.add('open'));
  close.addEventListener('click',  () => mobile.classList.remove('open'));
  mobile.querySelectorAll('a').forEach(a => a.addEventListener('click', () => mobile.classList.remove('open')));
})();

// ── Float CTA ─────────────────────────────────────
(function(){
  const el = document.getElementById('floatCta');
  if (!el) return;
  window.addEventListener('scroll', () => {
    el.classList.toggle('visible', window.scrollY > 500);
  }, {passive:true});
})();

// ── Live clock ────────────────────────────────────
(function(){
  const el = document.getElementById('clockTime');
  if (!el) return;
  function tick(){
    const d = new Date();
    const tz = 'Europe/Berlin';
    el.textContent = d.toLocaleTimeString('de-DE', {timeZone:tz, hour:'2-digit', minute:'2-digit', second:'2-digit'});
  }
  tick(); setInterval(tick, 1000);
})();

// ── Open/closed status ────────────────────────────
(function(){
  const el   = document.getElementById('openStatus');
  const text = document.getElementById('openStatusText');
  if (!el) return;
  const HOURS = {1:[10,20],2:[10,20],3:[10,20],4:[10,20],5:[9,18]};
  function update(){
    const now = new Date(new Date().toLocaleString('en-US',{timeZone:'Europe/Berlin'}));
    const wd  = now.getDay() === 0 ? 7 : now.getDay();
    const h   = HOURS[wd];
    if (!h){ el.className='open-status closed'; text.textContent=text.closest('[data-i18n]')? '':'Geschlossen'; return; }
    const cur = now.getHours() + now.getMinutes()/60;
    if (cur >= h[0] && cur < h[1]){
      el.className='open-status open';
      text.textContent = `Geöffnet · schließt ${h[1]}:00`;
    } else {
      el.className='open-status closed';
      const opens = Object.entries(HOURS).find(([d])=> parseInt(d) > wd);
      text.textContent = opens ? `Geschlossen · öffnet Di ${opens[1][0]}:00` : 'Geschlossen';
    }
  }
  update(); setInterval(update, 60000);
})();

// ── Counters ──────────────────────────────────────
(function(){
  function animateCounter(el, target, suffix=''){
    let v = 0;
    const step = () => {
      v += Math.ceil((target-v)/12) || 1;
      el.textContent = (v >= target ? target : v) + suffix;
      if (v < target) requestAnimationFrame(step);
    };
    step();
  }
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const years   = document.getElementById('counterYears');
      const clients = document.getElementById('counterClients');
      if (years)   animateCounter(years, 5, '+');
      if (clients) animateCounter(clients, 500, '+');
      obs.disconnect();
    });
  }, {threshold:.5});
  const target = document.querySelector('.hero-stats');
  if (target) obs.observe(target);
})();

// ── Scroll reveal ─────────────────────────────────
(function(){
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add('in'); obs.unobserve(e.target); }
    });
  }, {threshold:.12, rootMargin:'0px 0px -40px 0px'});
  document.querySelectorAll('.reveal,.reveal-left,.reveal-right').forEach(el => obs.observe(el));
})();

// ── Gallery ───────────────────────────────────────
(function(){
  const grid   = document.getElementById('galleryGrid');
  const filter = document.getElementById('worksFilter');
  if (!grid) return;

  let allPhotos = [];

  function renderGallery(cat){
    const items = cat ? allPhotos.filter(p => p.category === cat) : allPhotos;
    if (!items.length){
      grid.innerHTML = '<div class="gallery-item" style="aspect-ratio:1;display:flex;align-items:center;justify-content:center;color:var(--text-dim);font-size:.8rem">Keine Fotos</div>';
      return;
    }
    grid.innerHTML = items.map(p => `
      <div class="gallery-item reveal" data-cat="${p.category||''}">
        <img src="/uploads/${p.filename}" alt="${p.caption||''}" loading="lazy">
        <div class="gallery-overlay">
          <div class="gallery-caption">
            ${p.category ? `<strong>${p.category}</strong>` : ''}
            ${p.caption ? `<span>${p.caption}</span>` : ''}
          </div>
        </div>
      </div>
    `).join('');
    // Re-trigger reveal observer
    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting){ e.target.classList.add('in'); obs.unobserve(e.target); }});
    }, {threshold:.1});
    grid.querySelectorAll('.reveal').forEach(el => obs.observe(el));
  }

  function buildFilters(photos){
    const cats = [...new Set(photos.map(p => p.category).filter(Boolean))];
    const existing = [...filter.querySelectorAll('.filter-btn')];
    cats.forEach(cat => {
      if (!existing.find(b => b.dataset.cat === cat)){
        const btn = document.createElement('button');
        btn.className = 'filter-btn';
        btn.dataset.cat = cat;
        btn.textContent = cat;
        filter.appendChild(btn);
      }
    });
  }

  filter.addEventListener('click', e => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    filter.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderGallery(btn.dataset.cat);
  });

  fetch('/api/photos').then(r => r.json()).then(d => {
    allPhotos = d.photos || [];
    if (!allPhotos.length){
      grid.innerHTML = '<div class="gallery-item" style="grid-column:1/-1;aspect-ratio:unset;padding:3rem;display:flex;align-items:center;justify-content:center;color:var(--text-dim);font-size:.85rem;border-radius:var(--radius-lg)">Noch keine Fotos vorhanden</div>';
      return;
    }
    buildFilters(allPhotos);
    renderGallery('');
  }).catch(() => {
    grid.innerHTML = '';
  });
})();

// ── Booking form ──────────────────────────────────
(function(){
  const dateInput = document.getElementById('fDate');
  const slotsWrap = document.getElementById('slotsWrap');
  const timeInput = document.getElementById('fTime');
  const form      = document.getElementById('bookingForm');
  const modal     = document.getElementById('modalOverlay');
  const modalBtn  = document.getElementById('modalBtn');
  if (!dateInput) return;

  let fp;

  fetch('/api/availability').then(r => r.json()).then(d => {
    fp = flatpickr(dateInput, {
      locale: 'de',
      minDate: 'today',
      maxDate: new Date(Date.now() + 60*24*60*60*1000),
      disable: d.disabled || [],
      disableMobile: false,
      dateFormat: 'Y-m-d',
      altInput: true,
      altFormat: 'D, d. M Y',
      onChange: ([date]) => {
        if (!date) return;
        const ds = date.toISOString().slice(0,10);
        loadSlots(ds);
      }
    });
  });

  function loadSlots(dateStr){
    slotsWrap.innerHTML = '<span class="slot-hint">…</span>';
    timeInput.value = '';
    fetch('/api/slots?date=' + dateStr).then(r => r.json()).then(d => {
      if (d.closed || !d.slots.length){
        const L = window._L || {};
        slotsWrap.innerHTML = `<span class="slot-hint">${L.closed || 'Geschlossen / keine freien Slots'}</span>`;
        return;
      }
      slotsWrap.innerHTML = d.slots.map(s =>
        `<button type="button" class="slot-btn" data-time="${s}">${s}</button>`
      ).join('');
    });
  }

  slotsWrap.addEventListener('click', e => {
    const btn = e.target.closest('.slot-btn');
    if (!btn) return;
    slotsWrap.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    timeInput.value = btn.dataset.time;
  });

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = form.querySelector('.btn-submit');
    const name    = document.getElementById('fName').value.trim();
    const phone   = document.getElementById('fPhone').value.trim();
    const service = document.getElementById('fService').value;
    const date    = dateInput.value;
    const time    = timeInput.value;

    if (!name || !phone || !service || !date || !time) {
      btn.textContent = '⚠ Bitte alle Pflichtfelder ausfüllen';
      setTimeout(() => btn.setAttribute('data-i18n','f_submit') && setLang(localStorage.getItem('lang')||'de'), 2500);
      return;
    }

    btn.disabled = true;
    btn.textContent = '…';

    try {
      const res = await fetch('/api/book', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          name, phone,
          email:    document.getElementById('fEmail').value.trim(),
          telegram: document.getElementById('fTelegram').value.trim(),
          service, date, time,
          comment:  document.getElementById('fComment').value.trim(),
        })
      });
      const data = await res.json();
      if (data.success){
        modal.classList.add('show');
        form.reset();
        slotsWrap.innerHTML = '<span class="slot-hint" data-i18n="f_time_hint">Zuerst Datum wählen</span>';
        timeInput.value = '';
        if (fp) fp.clear();
      } else {
        btn.textContent = data.error || 'Fehler — bitte erneut versuchen';
        btn.disabled = false;
        setTimeout(() => { btn.disabled=false; setLang(localStorage.getItem('lang')||'de'); }, 3000);
      }
    } catch {
      btn.textContent = 'Netzwerkfehler';
      btn.disabled = false;
    }
  });

  if (modalBtn) modalBtn.addEventListener('click', () => modal.classList.remove('show'));
  modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('show'); });
})();

// ── i18n ─────────────────────────────────────────
const LANGS = {
  de: {
    nav_about:'Über uns', nav_works:'Arbeiten', nav_prices:'Preise', nav_book:'Termin',
    hero_eyebrow:'Premium Barber · München',
    hero_h1:'Dein Style,<br><em>Dein Auftritt</em>',
    hero_sub:'Fades, klassische Schnitte und Bartpflege — professionell und mit Leidenschaft seit 2019.',
    hero_cta:'Termin buchen', hero_works:'Arbeiten ansehen',
    stat_years:'Jahre Erfahrung', stat_clients:'Zufriedene Kunden',
    scroll_label:'Scroll',
    badge_title:'Premium Service', badge_sub:'München · seit 2019',
    about_eyebrow:'01 — Über uns', about_h2:'Handwerk &<br><em>Leidenschaft</em>',
    about_p1:'Spezialist für Fades, klassische Schnitte und Bartpflege. Über 5 Jahre Erfahrung und ein Auge fürs Detail — jeder Look auf ein neues Level.',
    about_ig:'Instagram ansehen ↗',
    skill1:'Fades & Skin Fades', skill2:'Klassische Schnitte', skill3:'Bartpflege & Rasur',
    work_eyebrow:'02 — Portfolio', work_h2:'Aktuelle<br><em>Arbeiten</em>',
    work_more:'Mehr auf Instagram ↗', cat_all:'Alle',
    prices_eyebrow:'03 — Preisliste', prices_h2:'Was ich<br><em>anbiete</em>',
    svc1:'Klassischer Haarschnitt', svc2:'Maschinenschnitt', svc3:'Fade / Skin Fade',
    svc4:'Schnitt + Bart', svc5:'Bartpflege', svc6:'Heißrasur',
    svc7:'Kinder (bis 12)', svc8:'Styling', svc9:'Graukaschierung', svc10:'Schnitt + Styling',
    prices_note:'* Alle Preise inkl. MwSt.', prices_btn:'Jetzt buchen',
    bk_eyebrow:'04 — Online Termin', bk_h2:'Wann<br><em>kommst du?</em>',
    bk_desc:'Wähle einen passenden Termin — die Bestätigung kommt sofort.',
    oh_title:'Öffnungszeiten', oh_mon:'Montag', oh_closed:'Geschlossen',
    oh_di:'Di — Fr', oh_sat:'Samstag', oh_sun:'Sonntag',
    form_title:'Termin <em>buchen</em>',
    f_name:'Name *', f_phone:'Telefon *', f_reminder:'Telegram',
    f_service:'Service *', f_service_ph:'Service wählen …',
    f_svc1:'Klassischer Haarschnitt — 25€', f_svc2:'Maschinenschnitt — 20€',
    f_svc3:'Fade / Skin Fade — 30€', f_svc4:'★ Schnitt + Bart — 40€',
    f_svc5:'Bartpflege — 20€', f_svc6:'Heißrasur — 30€',
    f_svc7:'Kinder (bis 12) — 20€', f_svc8:'Styling — 15€',
    f_svc9:'Graukaschierung — 35€', f_svc10:'Schnitt + Styling — 35€',
    f_date:'Datum *', f_time:'Uhrzeit *', f_time_hint:'Zuerst Datum wählen',
    f_date_ph:'Datum wählen', f_comment_ph:'Besondere Wünsche…',
    f_comment:'Notizen', f_submit:'Termin buchen ✂',
    modal_h3:'Termin bestätigt!', modal_msg:'Bis bald! Die Bestätigung kommt in Kürze.', modal_btn:'Super!',
    float_btn:'Buchen', wc_book:'Buchen ↗',
    closed:'Geschlossen / keine freien Slots',
  },
  ru: {
    nav_about:'О нас', nav_works:'Работы', nav_prices:'Цены', nav_book:'Запись',
    hero_eyebrow:'Премиум барбер · Мюнхен',
    hero_h1:'Твой стиль,<br><em>твой образ</em>',
    hero_sub:'Фейды, классические стрижки и уход за бородой — профессионально и с душой с 2019 года.',
    hero_cta:'Записаться', hero_works:'Смотреть работы',
    stat_years:'Лет опыта', stat_clients:'Довольных клиентов',
    scroll_label:'Листай',
    badge_title:'Премиум сервис', badge_sub:'Мюнхен · с 2019',
    about_eyebrow:'01 — О нас', about_h2:'Мастерство &<br><em>страсть</em>',
    about_p1:'Специалист по фейдам, классическим стрижкам и уходу за бородой. Более 5 лет опыта и внимание к деталям — каждый образ на новый уровень.',
    about_ig:'Instagram ↗',
    skill1:'Фейды & Скин Фейды', skill2:'Классические стрижки', skill3:'Уход за бородой',
    work_eyebrow:'02 — Портфолио', work_h2:'Последние<br><em>работы</em>',
    work_more:'Больше в Instagram ↗', cat_all:'Все',
    prices_eyebrow:'03 — Прайслист', prices_h2:'Что я<br><em>предлагаю</em>',
    svc1:'Классическая стрижка', svc2:'Стрижка машинкой', svc3:'Fade / Skin Fade',
    svc4:'Стрижка + Борода', svc5:'Уход за бородой', svc6:'Горячее бритьё',
    svc7:'Дети (до 12)', svc8:'Стайлинг', svc9:'Камуфляж седины', svc10:'Стрижка + Стайлинг',
    prices_note:'* Все цены вкл. НДС.', prices_btn:'Записаться сейчас',
    bk_eyebrow:'04 — Онлайн запись', bk_h2:'Когда<br><em>придёшь?</em>',
    bk_desc:'Выбери удобное время — подтверждение придёт сразу.',
    oh_title:'Часы работы', oh_mon:'Понедельник', oh_closed:'Закрыто',
    oh_di:'Вт — Пт', oh_sat:'Суббота', oh_sun:'Воскресенье',
    form_title:'Запись <em>онлайн</em>',
    f_name:'Имя *', f_phone:'Телефон *', f_reminder:'Telegram',
    f_service:'Услуга *', f_service_ph:'Выберите услугу ...',
    f_svc1:'Классическая стрижка — 25€', f_svc2:'Стрижка машинкой — 20€',
    f_svc3:'Fade / Skin Fade — 30€', f_svc4:'★ Стрижка + Борода — 40€',
    f_svc5:'Уход за бородой — 20€', f_svc6:'Горячее бритьё — 30€',
    f_svc7:'Дети (до 12) — 20€', f_svc8:'Стайлинг — 15€',
    f_svc9:'Камуфляж седины — 35€', f_svc10:'Стрижка + Стайлинг — 35€',
    f_date:'Дата *', f_time:'Время *', f_time_hint:'Сначала выберите дату',
    f_date_ph:'Выбрать дату', f_comment_ph:'Особые пожелания…',
    f_comment:'Примечание', f_submit:'Записаться ✂',
    modal_h3:'Запись подтверждена!', modal_msg:'До встречи! Подтверждение придёт скоро.', modal_btn:'Отлично!',
    float_btn:'✂ Записаться', wc_book:'Записаться ↗',
    closed:'Закрыто / нет свободных слотов',
  },
  uk: {
    nav_about:'Про нас', nav_works:'Роботи', nav_prices:'Ціни', nav_book:'Запис',
    hero_eyebrow:'Преміум барбер · Мюнхен',
    hero_h1:'Твій стиль,<br><em>твій образ</em>',
    hero_sub:'Фейди, класичні стрижки та догляд за бородою — професійно і з пристрастю з 2019 року.',
    hero_cta:'Записатися', hero_works:'Дивитися роботи',
    stat_years:'Років досвіду', stat_clients:'Задоволених клієнтів',
    scroll_label:'Гортай',
    badge_title:'Преміум сервіс', badge_sub:'Мюнхен · з 2019',
    about_eyebrow:'01 — Про нас', about_h2:'Майстерність &<br><em>пристрасть</em>',
    about_p1:'Спеціаліст з фейдів, класичних стрижок та догляду за бородою. Понад 5 років досвіду — кожен образ на новий рівень.',
    about_ig:'Дивитися Instagram ↗',
    skill1:'Фейди & Скін Фейди', skill2:'Класичні стрижки', skill3:'Догляд за бородою',
    work_eyebrow:'02 — Портфоліо', work_h2:'Останні<br><em>роботи</em>',
    work_more:'Більше в Instagram ↗', cat_all:'Всі',
    prices_eyebrow:'03 — Прайс-ліст', prices_h2:'Що я<br><em>пропоную</em>',
    svc1:'Класична стрижка', svc2:'Стрижка машинкою', svc3:'Fade / Skin Fade',
    svc4:'Стрижка + Борода', svc5:'Догляд за бородою', svc6:'Гаряче гоління',
    svc7:'Діти (до 12)', svc8:'Стайлінг', svc9:'Камуфляж сивини', svc10:'Стрижка + Стайлінг',
    prices_note:'* Всі ціни вкл. ПДВ.', prices_btn:'Записатися зараз',
    bk_eyebrow:'04 — Онлайн запис', bk_h2:'Коли<br><em>прийдеш?</em>',
    bk_desc:'Оберіть зручний час — підтвердження надійде одразу.',
    oh_title:'Години роботи', oh_mon:'Понеділок', oh_closed:'Зачинено',
    oh_di:'Вт — Пт', oh_sat:'Субота', oh_sun:'Неділя',
    form_title:'Запис <em>онлайн</em>',
    f_name:"Ім'я *", f_phone:'Телефон *', f_reminder:'Telegram',
    f_service:'Послуга *', f_service_ph:'Оберіть послугу ...',
    f_svc1:'Класична стрижка — 25€', f_svc2:'Стрижка машинкою — 20€',
    f_svc3:'Fade / Skin Fade — 30€', f_svc4:'★ Стрижка + Борода — 40€',
    f_svc5:'Догляд за бородою — 20€', f_svc6:'Гаряче гоління — 30€',
    f_svc7:'Діти (до 12) — 20€', f_svc8:'Стайлінг — 15€',
    f_svc9:'Камуфляж сивини — 35€', f_svc10:'Стрижка + Стайлінг — 35€',
    f_date:'Дата *', f_time:'Час *', f_time_hint:'Спочатку дату',
    f_date_ph:'Обрати дату', f_comment_ph:'Особливі побажання…',
    f_comment:'Примітки', f_submit:'Записатися ✂',
    modal_h3:'Запис підтверджено!', modal_msg:'До зустрічі! Підтвердження надійде незабаром.', modal_btn:'Чудово!',
    float_btn:'✂ Записатися', wc_book:'Записатися ↗',
    closed:'Зачинено / немає вільних слотів',
  }
};

window._L = LANGS.de;

function setLang(lang){
  if (!LANGS[lang]) return;
  const L = LANGS[lang];
  window._L = L;
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

  // Update flatpickr locale
  if (window.flatpickr && document.getElementById('fDate')?._flatpickr){
    const fp = document.getElementById('fDate')._flatpickr;
    const locale = lang === 'de' ? 'de' : 'default';
    fp.set('locale', locale);
  }
}

document.querySelectorAll('.lang-sw button').forEach(b =>
  b.addEventListener('click', () => setLang(b.dataset.lang))
);
setLang(localStorage.getItem('lang') || 'de');
