(() => {
  'use strict';
  const track = document.getElementById('photo-track');
  const dialog = document.getElementById('photo-dialog');
  if (!track || !dialog) return;
  const photos = Array.from(track.querySelectorAll('[data-gallery-photo]'));
  if (!photos.length) return;
  const image = document.getElementById('photo-dialog-image');
  const title = document.getElementById('photo-dialog-title');
  const count = document.getElementById('photo-dialog-count');
  const original = document.getElementById('photo-dialog-original');
  const stage = dialog.querySelector('.photo-dialog__stage');
  const previous = document.getElementById('photo-scroll-previous');
  const next = document.getElementById('photo-scroll-next');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let active = 0;
  let pointerStart = null;
  let backdropStart = false;

  function setHash(hash) {
    const url = new URL(window.location.href);
    url.hash = hash;
    window.history.replaceState(null, '', url);
  }

  function showPhoto(index, updateHash = true) {
    active = (index + photos.length) % photos.length;
    const photo = photos[active];
    image.src = photo.href;
    image.alt = photo.querySelector('img').alt;
    title.textContent = photo.dataset.title;
    count.textContent = `${String(active + 1).padStart(2, '0')} / ${String(photos.length).padStart(2, '0')}`;
    original.href = photo.dataset.original;
    if (updateHash) setHash(photo.id);
  }

  function openPhoto(index, updateHash = true) {
    if (typeof dialog.showModal !== 'function') return false;
    showPhoto(index, updateHash);
    if (!dialog.open) {
      dialog.showModal();
      document.documentElement.classList.add('photo-dialog-open');
      document.querySelectorAll('video').forEach(video => video.pause());
    }
    return true;
  }

  photos.forEach((photo, index) => {
    photo.addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      if (openPhoto(index)) event.preventDefault();
    });
  });

  document.getElementById('photo-dialog-close').addEventListener('click', () => dialog.close());
  document.getElementById('photo-dialog-previous').addEventListener('click', () => showPhoto(active - 1));
  document.getElementById('photo-dialog-next').addEventListener('click', () => showPhoto(active + 1));
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      showPhoto(active + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  dialog.addEventListener('pointerdown', event => { backdropStart = event.target === dialog; });
  dialog.addEventListener('click', event => {
    if (backdropStart && event.target === dialog) {
      const rect = dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
    }
    backdropStart = false;
  });
  dialog.addEventListener('close', () => {
    pointerStart = null;
    document.documentElement.classList.remove('photo-dialog-open');
    if (photos.some(photo => `#${photo.id}` === window.location.hash)) setHash('photo-gallery');
  });

  stage.addEventListener('pointerdown', event => {
    if (event.pointerType !== 'touch' || event.target.closest('button')) return;
    pointerStart = {x: event.clientX, y: event.clientY};
    stage.setPointerCapture(event.pointerId);
  });
  stage.addEventListener('pointerup', event => {
    if (!pointerStart) return;
    const dx = event.clientX - pointerStart.x;
    const dy = event.clientY - pointerStart.y;
    pointerStart = null;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) showPhoto(active + (dx < 0 ? 1 : -1));
  });
  stage.addEventListener('pointercancel', () => { pointerStart = null; });

  function updateArrows() {
    previous.disabled = track.scrollLeft <= 2;
    next.disabled = track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
  }
  function scrollPhotos(direction) {
    const distance = photos[0].getBoundingClientRect().width + parseFloat(getComputedStyle(track).gap || 0);
    track.scrollBy({left: direction * distance, behavior: reducedMotion.matches ? 'auto' : 'smooth'});
  }
  previous.addEventListener('click', () => scrollPhotos(-1));
  next.addEventListener('click', () => scrollPhotos(1));
  track.addEventListener('scroll', updateArrows, {passive: true});
  track.addEventListener('keydown', event => {
    if (event.target === track && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
      event.preventDefault();
      scrollPhotos(event.key === 'ArrowRight' ? 1 : -1);
    }
  });
  window.addEventListener('resize', updateArrows);
  updateArrows();

  function openHash() {
    const index = photos.findIndex(photo => `#${photo.id}` === window.location.hash);
    if (index >= 0) openPhoto(index, false);
    else if (dialog.open) dialog.close();
  }
  window.addEventListener('hashchange', openHash);
  openHash();
})();
