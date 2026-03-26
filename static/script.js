// ══════════════════════════════════════════════════════
//   BarberShop — Main Script
// ══════════════════════════════════════════════════════

// ── Clock ────────────────────────────────────────────

const DAYS = ['Воскресенье','Понедельник','Вторник','Среда','Четверг','Пятница','Суббота'];
const MONTHS = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];

function updateClock() {
  const now = new Date();
  const timeEl = document.getElementById('clockTime');
  const dateEl = document.getElementById('clockDate');
  if (timeEl) timeEl.textContent = now.toLocaleTimeString('ru-RU');
  if (dateEl) dateEl.textContent =
    `${DAYS[now.getDay()]}, ${now.getDate()} ${MONTHS[now.getMonth()]} ${now.getFullYear()}`;
}
updateClock();
setInterval(updateClock, 1000);

// ── Work hours indicator ─────────────────────────────

function updateWorkIndicator() {
  const el = document.getElementById('workIndicator');
  if (!el) return;
  const now = new Date();
  const wd = now.getDay(); // 0=Sun, 6=Sat
  const h = now.getHours() + now.getMinutes() / 60;
  let open = false, openStr = '';

  if (wd >= 1 && wd <= 5) { open = h >= 9 && h < 20; openStr = '9:00–20:00'; }
  else if (wd === 6)       { open = h >= 10 && h < 19; openStr = '10:00–19:00'; }
  else                     { open = h >= 10 && h < 17; openStr = '10:00–17:00'; }

  el.className = 'work-indicator ' + (open ? 'open' : 'closed');
  el.textContent = open
    ? `🟢 Сейчас открыто (до ${openStr.split('–')[1]})`
    : `🔴 Сейчас закрыто · Часы работы: ${openStr}`;
}
updateWorkIndicator();
setInterval(updateWorkIndicator, 60000);

// ── Navbar scroll effect ─────────────────────────────

const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar && (window.scrollY > 60
    ? navbar.classList.add('scrolled')
    : navbar.classList.remove('scrolled'));
}, { passive: true });

// ── Mobile menu ──────────────────────────────────────

function toggleMenu() {
  const menu = document.getElementById('mobileMenu');
  const btn = document.getElementById('hamburger');
  if (!menu) return;
  menu.classList.toggle('open');
  btn && btn.classList.toggle('active');
  document.body.style.overflow = menu.classList.contains('open') ? 'hidden' : '';
}

// ── Booking: date setup ──────────────────────────────

const dateInput = document.getElementById('bookDate');
if (dateInput) {
  const today = new Date();
  const maxDate = new Date(today);
  maxDate.setDate(today.getDate() + 30);
  dateInput.min = today.toISOString().split('T')[0];
  dateInput.max = maxDate.toISOString().split('T')[0];
  dateInput.addEventListener('change', loadTimeSlots);
}

// ── Booking: time slots ──────────────────────────────

async function loadTimeSlots() {
  const date = document.getElementById('bookDate').value;
  const sel = document.getElementById('bookTime');
  if (!date || !sel) return;

  sel.innerHTML = '<option value="">Загрузка...</option>';
  sel.disabled = true;

  try {
    const res = await fetch(`/api/slots?date=${date}`);
    const data = await res.json();

    sel.innerHTML = '';
    if (!data.slots || !data.slots.length) {
      sel.innerHTML = '<option value="">Нет свободных слотов</option>';
    } else {
      const placeholder = document.createElement('option');
      placeholder.value = ''; placeholder.textContent = 'Выберите время';
      sel.appendChild(placeholder);
      data.slots.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s; opt.textContent = s;
        sel.appendChild(opt);
      });
    }
  } catch {
    sel.innerHTML = '<option value="">Ошибка загрузки</option>';
  } finally {
    sel.disabled = false;
  }
}

// ── Booking form submit ──────────────────────────────

const bookingForm = document.getElementById('bookingForm');
if (bookingForm) {
  bookingForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('submitBtn');
    const origText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Отправляем...';

    const payload = {
      name:     document.getElementById('bookName').value.trim(),
      phone:    document.getElementById('bookPhone').value.trim(),
      email:    document.getElementById('bookEmail').value.trim(),
      telegram: document.getElementById('bookTelegram').value.trim(),
      service:  document.getElementById('bookService').value,
      date:     document.getElementById('bookDate').value,
      time:     document.getElementById('bookTime').value,
      comment:  document.getElementById('bookComment').value.trim(),
    };

    try {
      const res = await fetch('/api/book', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (data.success) {
        document.getElementById('modalMsg').textContent = data.message;
        showModal();
        bookingForm.reset();
        document.getElementById('bookTime').innerHTML = '<option value="">Сначала выберите дату</option>';
      } else {
        showError(data.error || 'Произошла ошибка');
      }
    } catch {
      showError('Ошибка соединения с сервером');
    } finally {
      btn.disabled = false;
      btn.textContent = origText;
    }
  });
}

function showError(msg) {
  const existing = document.querySelector('.form-error');
  if (existing) existing.remove();
  const el = document.createElement('div');
  el.className = 'form-error';
  el.style.cssText = 'color:#ef4444;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:8px;padding:0.75rem 1rem;font-size:0.85rem;margin-bottom:1rem;';
  el.textContent = '⚠ ' + msg;
  bookingForm.insertBefore(el, bookingForm.querySelector('button[type=submit]'));
  setTimeout(() => el.remove(), 5000);
}

// ── Modal ────────────────────────────────────────────

function showModal() {
  document.getElementById('modal').classList.add('show');
  document.getElementById('overlay').classList.add('show');
}
function closeModal() {
  document.getElementById('modal').classList.remove('show');
  document.getElementById('overlay').classList.remove('show');
}

// ── Scroll reveal ────────────────────────────────────

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry, i) => {
    if (entry.isIntersecting) {
      setTimeout(() => {
        entry.target.classList.add('in');
        // Animate skill bars
        entry.target.querySelectorAll('.skill-fill').forEach(bar => {
          bar.style.width = (bar.dataset.w || 0) + '%';
        });
      }, i * 80);
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.12 });

document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
