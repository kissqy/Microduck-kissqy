(() => {
  'use strict';
  const wall = document.getElementById('photo-track');
  if (!wall) return;
  const cards = Array.from(wall.querySelectorAll('[data-media-card]'));
  const videos = Array.from(wall.querySelectorAll('video'));
  const filters = Array.from(document.querySelectorAll('[data-media-filter]'));
  const count = document.getElementById('media-count');
  const photos = Array.from(wall.querySelectorAll('[data-gallery-photo]'));
  const dialog = document.getElementById('photo-dialog');
  const image = document.getElementById('photo-dialog-image');
  const title = document.getElementById('photo-dialog-title');
  const photoCount = document.getElementById('photo-dialog-count');
  const original = document.getElementById('photo-dialog-original');
  let frame = 0, lastWidth = -1, activePhoto = 0, lastFocused = null;

  function layout() {
    frame = 0;
    const width = wall.clientWidth;
    if (!width) return;
    lastWidth = width;
    const gap = width < 600 ? 14 : 20;
    const columns = width >= 1100 ? 4 : width >= 800 ? 3 : width >= 520 ? 2 : 1;
    const cardWidth = (width - gap * (columns - 1)) / columns;
    const visible = cards.filter(card => !card.hidden);
    visible.forEach(card => { card.style.width = `${cardWidth}px`; });
    const heights = Array(columns).fill(0);
    const positions = visible.map(card => {
      const column = heights.indexOf(Math.min(...heights));
      const y = heights[column];
      heights[column] += card.offsetHeight + gap;
      return {card, x: column * (cardWidth + gap), y};
    });
    wall.classList.add('masonry-ready');
    positions.forEach(({card, x, y}) => {
      card.style.transform = `translate3d(${x}px,${y}px,0)`;
    });
    wall.style.height = `${Math.max(0, ...heights) - (visible.length ? gap : 0)}px`;
  }

  function scheduleLayout() {
    if (!frame) frame = requestAnimationFrame(layout);
  }

  function filterMedia(kind) {
    cards.forEach(card => {
      card.hidden = kind !== 'all' && card.dataset.kind !== kind;
      if (card.hidden) card.querySelector('video')?.pause();
    });
    filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.mediaFilter === kind)));
    const visible = cards.filter(card => !card.hidden);
    const videoCount = visible.filter(card => card.dataset.kind === 'video').length;
    const imageCount = visible.length - videoCount;
    count.textContent = kind === 'video' ? `${videoCount} 个视频` : kind === 'photo' ? `${imageCount} 张照片` : `${videoCount} 个视频 · ${imageCount} 张照片`;
    scheduleLayout();
  }
  filters.forEach(button => button.addEventListener('click', () => filterMedia(button.dataset.mediaFilter)));

  if ('ResizeObserver' in window) {
    const observedHeights = new WeakMap();
    const resize = new ResizeObserver(entries => {
      if (entries.some(entry => {
        if (entry.target === wall) return Math.abs(entry.contentRect.width - lastWidth) > 0.5;
        const previous = observedHeights.get(entry.target);
        observedHeights.set(entry.target, entry.contentRect.height);
        return previous === undefined || Math.abs(previous - entry.contentRect.height) > 0.5;
      })) scheduleLayout();
    });
    resize.observe(wall);
    cards.forEach(card => resize.observe(card));
  }
  window.addEventListener('resize', scheduleLayout, {passive: true});
  wall.querySelectorAll('img').forEach(img => img.addEventListener('load', scheduleLayout));

  videos.forEach(video => {
    video.addEventListener('loadedmetadata', () => {
      if (video.videoWidth && video.videoHeight) video.style.aspectRatio = `${video.videoWidth}/${video.videoHeight}`;
      scheduleLayout();
    });
    video.addEventListener('play', () => videos.forEach(other => { if (other !== video) other.pause(); }));
    video.addEventListener('error', () => {
      video.closest('[data-media-card]').querySelector('.media-error').hidden = false;
      scheduleLayout();
    });
  });
  if ('IntersectionObserver' in window) {
    const lazy = new IntersectionObserver(entries => entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const video = entry.target;
      video.preload = 'metadata';
      if (video.readyState === 0 && video.paused) video.load();
      lazy.unobserve(video);
    }), {rootMargin: '400px 0px'});
    videos.forEach(video => lazy.observe(video));
  }

  function setHash(hash) {
    const url = new URL(location.href);
    url.hash = hash;
    history.replaceState(null, '', url);
  }
  function showPhoto(index, updateHash = true) {
    activePhoto = (index + photos.length) % photos.length;
    const photo = photos[activePhoto];
    image.src = photo.href;
    image.alt = photo.querySelector('img').alt;
    title.textContent = photo.dataset.title;
    photoCount.textContent = `${activePhoto + 1} / ${photos.length}`;
    original.href = photo.dataset.original;
    if (updateHash) setHash(photo.id);
  }
  function openPhoto(index, updateHash = true) {
    if (!dialog || typeof dialog.showModal !== 'function') return false;
    lastFocused = document.activeElement;
    showPhoto(index, updateHash);
    videos.forEach(video => video.pause());
    if (!dialog.open) dialog.showModal();
    document.documentElement.classList.add('photo-dialog-open');
    return true;
  }
  photos.forEach((photo, index) => photo.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
    if (openPhoto(index)) event.preventDefault();
  }));
  if (dialog) {
    document.getElementById('photo-dialog-close').addEventListener('click', () => dialog.close());
    document.getElementById('photo-dialog-previous').addEventListener('click', () => showPhoto(activePhoto - 1));
    document.getElementById('photo-dialog-next').addEventListener('click', () => showPhoto(activePhoto + 1));
    dialog.addEventListener('keydown', event => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
      event.preventDefault();
      showPhoto(activePhoto + (event.key === 'ArrowRight' ? 1 : -1));
    });
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const box = dialog.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
    });
    dialog.addEventListener('close', () => {
      document.documentElement.classList.remove('photo-dialog-open');
      if (photos.some(photo => `#${photo.id}` === location.hash)) setHash('photo-gallery');
      lastFocused?.focus({preventScroll: true});
    });
    const stage = dialog.querySelector('.photo-dialog__stage');
    let start = null;
    stage.addEventListener('pointerdown', event => {
      if (event.pointerType === 'touch' && !event.target.closest('button')) start = {x:event.clientX,y:event.clientY};
    });
    stage.addEventListener('pointerup', event => {
      if (!start) return;
      const dx = event.clientX - start.x, dy = event.clientY - start.y;
      start = null;
      if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) showPhoto(activePhoto + (dx < 0 ? 1 : -1));
    });
    stage.addEventListener('pointercancel', () => { start = null; });
  }
  function openHash() {
    const hash = location.hash;
    const photoIndex = photos.findIndex(photo => `#${photo.id}` === hash);
    if (photoIndex >= 0) { filterMedia('photo'); openPhoto(photoIndex, false); }
    else if (hash === '#photo-gallery') filterMedia('photo');
    else if (hash === '#more-videos' || hash === '#balance-video') filterMedia('video');
  }
  window.addEventListener('hashchange', openHash);
  filterMedia('all');
  openHash();
})();
