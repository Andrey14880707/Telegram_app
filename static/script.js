/* ═══════════════════════════════════════════════════
   MÜNCHEN BARBER — Main Script
   ═══════════════════════════════════════════════════ */

// ── Preloader ────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  const fill = document.getElementById('plFill');
  const pl   = document.getElementById('preloader');
  if (!pl) return;
  if (fill) fill.style.width = '100%';
  setTimeout(() => pl.classList.add('out'), 1800);
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
  // inline (mobile)
  const mob = document.getElementById('heroTime');
  if (mob) mob.textContent = t;
  // desktop (absolute)
  const desk = document.getElementById('heroTimeDesk');
  if (desk) desk.textContent = t;
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
  el.className = 'bk-status ' + (open ? 'open' : 'closed');
  el.textContent = open ? '🟢 Jetzt geöffnet' : '🔴 Aktuell geschlossen';
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

// ── Booking: date init ────────────────────────────────
const dateInput = document.getElementById('bDate');
if (dateInput) {
  const today  = new Date();
  const maxDay = new Date(today); maxDay.setDate(today.getDate() + 60);
  const fmt = d => d.toISOString().split('T')[0];
  dateInput.min = fmt(today);
  dateInput.max = fmt(maxDay);
  dateInput.addEventListener('change', loadSlots);
}

// ── Time slots ────────────────────────────────────────
async function loadSlots() {
  const date = document.getElementById('bDate').value;
  const sel  = document.getElementById('bTime');
  if (!date || !sel) return;

  sel.innerHTML = '<option value="">Lädt...</option>';
  sel.disabled = true;

  try {
    const res  = await fetch(`/api/slots?date=${date}`);
    const data = await res.json();

    sel.innerHTML = '';
    if (data.closed) {
      sel.innerHTML = '<option value="">Geschlossen (kein Termin)</option>';
    } else if (!data.slots?.length) {
      sel.innerHTML = '<option value="">Keine freien Zeiten</option>';
    } else {
      sel.appendChild(new Option('Uhrzeit wählen', ''));
      data.slots.forEach(s => sel.appendChild(new Option(s, s)));
    }
  } catch {
    sel.innerHTML = '<option value="">Fehler beim Laden</option>';
  } finally {
    sel.disabled = false;
  }
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
        document.getElementById('bTime').innerHTML = '<option value="">Erst Datum wählen</option>';
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
