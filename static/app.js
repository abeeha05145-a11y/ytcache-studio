// YTCache Studio - Professional 3D Animated Application Engine & Navigation Suite

document.addEventListener('DOMContentLoaded', () => {
  // Global State
  let currentVideoUrl = '';
  let currentVideoData = null;
  let currentTranscriptData = null;
  let activePollInterval = null;
  let updateTheme3DHandler = null;

  // -------------------------------------------------------------
  // 1. Futuristic Dynamic 3D Background (Three.js with Dark/Light Support)
  // -------------------------------------------------------------
  function init3DBackground() {
    const canvas = document.getElementById('bg-3d-canvas');
    if (!canvas || typeof THREE === 'undefined') return;

    let width = window.innerWidth;
    let height = window.innerHeight;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, width / height, 1, 1000);
    camera.position.z = 400;

    const renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Particle Cloud Setup
    const particleCount = 1000;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    // Initial Positions
    for (let i = 0; i < particleCount; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 1100;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 750;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 750;
    }
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    // Helper: Generate crisp circular particle textures
    function createParticleTexture(isDark) {
      const pCanvas = document.createElement('canvas');
      pCanvas.width = 64;
      pCanvas.height = 64;
      const ctx = pCanvas.getContext('2d');
      const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);

      if (isDark) {
        grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
        grad.addColorStop(0.35, 'rgba(165, 180, 252, 0.9)');
        grad.addColorStop(0.7, 'rgba(99, 102, 241, 0.4)');
        grad.addColorStop(1, 'rgba(99, 102, 241, 0.0)');
      } else {
        // High contrast for light mode
        grad.addColorStop(0, 'rgba(30, 27, 75, 1)');
        grad.addColorStop(0.4, 'rgba(49, 46, 129, 0.95)');
        grad.addColorStop(0.75, 'rgba(67, 56, 202, 0.6)');
        grad.addColorStop(1, 'rgba(67, 56, 202, 0.0)');
      }

      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 64, 64);
      return new THREE.CanvasTexture(pCanvas);
    }

    // Material
    const material = new THREE.PointsMaterial({
      size: 5.5,
      vertexColors: true,
      map: createParticleTexture(true),
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const particles = new THREE.Points(geometry, material);
    scene.add(particles);

    // Dynamic 3D Geometric Mesh / Constellation Lines
    const maxLineConnections = 300;
    const linePositions = new Float32Array(maxLineConnections * 6);
    const lineGeometry = new THREE.BufferGeometry();
    lineGeometry.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));

    const lineMaterial = new THREE.LineBasicMaterial({
      color: 0x818cf8,
      transparent: true,
      opacity: 0.25,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

    const lineMesh = new THREE.LineSegments(lineGeometry, lineMaterial);
    scene.add(lineMesh);

    // Theme Color Palettes
    const darkPalette = [
      new THREE.Color(0x00f2fe),
      new THREE.Color(0x818cf8),
      new THREE.Color(0xf43f5e),
      new THREE.Color(0xa855f7),
      new THREE.Color(0xffffff)
    ];

    const lightPalette = [
      new THREE.Color(0x1e1b4b),
      new THREE.Color(0x1d4ed8),
      new THREE.Color(0x6b21a8),
      new THREE.Color(0x0f766e),
      new THREE.Color(0x991b1b)
    ];

    function updateThemeColors(isDark) {
      const palette = isDark ? darkPalette : lightPalette;

      for (let i = 0; i < particleCount; i++) {
        const color = palette[i % palette.length];
        colors[i * 3] = color.r;
        colors[i * 3 + 1] = color.g;
        colors[i * 3 + 2] = color.b;
      }
      geometry.attributes.color.needsUpdate = true;

      material.map = createParticleTexture(isDark);
      material.needsUpdate = true;

      if (isDark) {
        material.blending = THREE.AdditiveBlending;
        material.opacity = 0.85;
        material.size = 5.2;

        lineMaterial.color.setHex(0x818cf8);
        lineMaterial.opacity = 0.28;
        lineMaterial.blending = THREE.AdditiveBlending;
        lineMaterial.needsUpdate = true;
      } else {
        material.blending = THREE.NormalBlending;
        material.opacity = 0.95;
        material.size = 6.2;

        lineMaterial.color.setHex(0x312e81);
        lineMaterial.opacity = 0.35;
        lineMaterial.blending = THREE.NormalBlending;
        lineMaterial.needsUpdate = true;
      }
    }

    updateTheme3DHandler = updateThemeColors;

    const initialIsDark = document.documentElement.classList.contains('dark');
    updateThemeColors(initialIsDark);

    // Mouse Tracking with smooth parallax
    let mouseX = 0;
    let mouseY = 0;
    let targetX = 0;
    let targetY = 0;

    window.addEventListener('mousemove', (e) => {
      mouseX = (e.clientX - width / 2) * 0.45;
      mouseY = (e.clientY - height / 2) * 0.45;
    });

    window.addEventListener('touchmove', (e) => {
      if (e.touches.length > 0) {
        mouseX = (e.touches[0].clientX - width / 2) * 0.45;
        mouseY = (e.touches[0].clientY - height / 2) * 0.45;
      }
    }, { passive: true });

    window.addEventListener('resize', () => {
      width = window.innerWidth;
      height = window.innerHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    });

    // Animation Loop
    let clock = new THREE.Clock();
    function animate() {
      requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime();

      targetX += (mouseX - targetX) * 0.04;
      targetY += (mouseY - targetY) * 0.04;

      camera.position.x = targetX * 0.45;
      camera.position.y = -targetY * 0.45;
      camera.lookAt(scene.position);

      particles.rotation.y = elapsedTime * 0.04;
      particles.rotation.x = Math.sin(elapsedTime * 0.02) * 0.08;

      lineMesh.rotation.y = particles.rotation.y;
      lineMesh.rotation.x = particles.rotation.x;

      let lineVertexIdx = 0;
      const posArray = geometry.attributes.position.array;
      const step = 8;
      for (let i = 0; i < 180; i += step) {
        for (let j = i + step; j < 180; j += step) {
          const dx = posArray[i * 3] - posArray[j * 3];
          const dy = posArray[i * 3 + 1] - posArray[j * 3 + 1];
          const dz = posArray[i * 3 + 2] - posArray[j * 3 + 2];
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

          if (dist < 130 && lineVertexIdx < maxLineConnections * 6) {
            linePositions[lineVertexIdx++] = posArray[i * 3];
            linePositions[lineVertexIdx++] = posArray[i * 3 + 1];
            linePositions[lineVertexIdx++] = posArray[i * 3 + 2];

            linePositions[lineVertexIdx++] = posArray[j * 3];
            linePositions[lineVertexIdx++] = posArray[j * 3 + 1];
            linePositions[lineVertexIdx++] = posArray[j * 3 + 2];
          }
        }
      }
      lineGeometry.attributes.position.needsUpdate = true;

      renderer.render(scene, camera);
    }

    animate();
  }

  init3DBackground();

  // -------------------------------------------------------------
  // 2. Button Ripple Effect (Micro-Interactions)
  // -------------------------------------------------------------
  document.addEventListener('click', (e) => {
    const targetBtn = e.target.closest('.btn-ripple');
    if (!targetBtn) return;

    const rect = targetBtn.getBoundingClientRect();
    const ripple = document.createElement('span');
    ripple.className = 'ripple-effect';

    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;

    ripple.style.width = `${size}px`;
    ripple.style.height = `${size}px`;
    ripple.style.left = `${x}px`;
    ripple.style.top = `${y}px`;

    targetBtn.appendChild(ripple);

    setTimeout(() => {
      ripple.remove();
    }, 600);
  });

  // -------------------------------------------------------------
  // 3. Theme Management (Seamless Dark / Light Mode Switch)
  // -------------------------------------------------------------
  const themeToggleBtn = document.getElementById('theme-toggle');
  function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const isDark = (savedTheme !== 'light');
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    if (updateTheme3DHandler) {
      updateTheme3DHandler(isDark);
    }
  }

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
      const isCurrentlyDark = document.documentElement.classList.contains('dark');
      const newIsDark = !isCurrentlyDark;

      if (newIsDark) {
        document.documentElement.classList.add('dark');
        localStorage.setItem('theme', 'dark');
      } else {
        document.documentElement.classList.remove('dark');
        localStorage.setItem('theme', 'light');
      }

      if (updateTheme3DHandler) {
        updateTheme3DHandler(newIsDark);
      }
    });
  }
  initTheme();

  // -------------------------------------------------------------
  // 4. Sidebar Drawer & Dedicated Navigation Modals (Smooth Transition)
  // -------------------------------------------------------------
  const menuToggleBtn = document.getElementById('menu-toggle-btn');
  const sidebarBackdrop = document.getElementById('sidebar-backdrop');
  const sidebarDrawer = document.getElementById('sidebar-drawer');
  const closeSidebarBtn = document.getElementById('close-sidebar-btn');
  const hamburgerLine1 = document.getElementById('hamburger-line-1');
  const hamburgerLine2 = document.getElementById('hamburger-line-2');
  const hamburgerLine3 = document.getElementById('hamburger-line-3');

  const infoModal = document.getElementById('info-modal');
  const infoModalCard = document.getElementById('info-modal-card');
  const closeInfoModalBtn = document.getElementById('close-info-modal-btn');
  const infoModalDoneBtn = document.getElementById('info-modal-done-btn');
  const infoModalTitle = document.getElementById('info-modal-title');
  const infoModalSubtitle = document.getElementById('info-modal-subtitle');
  const infoModalIconContainer = document.getElementById('info-modal-icon-container');
  const infoModalContent = document.getElementById('info-modal-content');

  let isSidebarOpen = false;

  function openSidebar() {
    isSidebarOpen = true;
    if (sidebarBackdrop) {
      sidebarBackdrop.classList.remove('hidden');
      requestAnimationFrame(() => {
        sidebarBackdrop.classList.remove('opacity-0');
        sidebarBackdrop.classList.add('opacity-100');
      });
    }
    if (sidebarDrawer) {
      sidebarDrawer.classList.remove('translate-x-full');
      sidebarDrawer.classList.add('translate-x-0');
    }
    document.body.classList.add('overflow-hidden');

    if (hamburgerLine1) hamburgerLine1.classList.add('rotate-45', 'translate-y-1.5');
    if (hamburgerLine2) hamburgerLine2.classList.add('opacity-0');
    if (hamburgerLine3) hamburgerLine3.classList.add('-rotate-45', '-translate-y-1.5');
  }

  function closeSidebar() {
    isSidebarOpen = false;
    if (sidebarDrawer) {
      sidebarDrawer.classList.remove('translate-x-0');
      sidebarDrawer.classList.add('translate-x-full');
    }
    if (sidebarBackdrop) {
      sidebarBackdrop.classList.remove('opacity-100');
      sidebarBackdrop.classList.add('opacity-0');
      setTimeout(() => {
        sidebarBackdrop.classList.add('hidden');
      }, 300);
    }
    document.body.classList.remove('overflow-hidden');

    if (hamburgerLine1) hamburgerLine1.classList.remove('rotate-45', 'translate-y-1.5');
    if (hamburgerLine2) hamburgerLine2.classList.remove('opacity-0');
    if (hamburgerLine3) hamburgerLine3.classList.remove('-rotate-45', '-translate-y-1.5');
  }

  if (menuToggleBtn) {
    menuToggleBtn.addEventListener('click', () => {
      if (isSidebarOpen) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });
  }

  if (closeSidebarBtn) closeSidebarBtn.addEventListener('click', closeSidebar);
  if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', closeSidebar);

  // Dedicated Pages Content (100% Professional SaaS English)
  const pagesData = {
    about: {
      title: "About YTCache Studio Pro",
      subtitle: "Platform Architecture & High-Performance Media Pipeline",
      icon: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`,
      content: `
        <div class="space-y-4">
          <div class="flex items-center gap-4 p-4 rounded-2xl bg-cyan-500/10 border border-cyan-500/25">
            <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/30 flex-shrink-0">
              <i class="fa-solid fa-play text-white text-lg ml-0.5"></i>
            </div>
            <div>
              <h3 class="text-base font-bold tracking-wide bg-gradient-to-r from-cyan-500 to-blue-500 dark:from-cyan-400 dark:to-blue-400 bg-clip-text text-transparent">YTCache Studio</h3>
              <p class="text-xs text-cyan-600 dark:text-cyan-400 font-bold">Universal 4K Downloader &amp; Transcript Suite</p>
            </div>
          </div>
          <p class="text-sm font-semibold leading-relaxed">
            <strong>YTCache Studio Pro</strong> is a state-of-the-art web utility built for creators, researchers, educators, and power users who demand rapid media archiving and instant spoken transcript generation.
          </p>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 my-4">
            <div class="p-4 rounded-2xl bg-indigo-500/10 border border-indigo-500/20">
              <h4 class="font-bold text-indigo-700 dark:text-indigo-300 text-sm mb-1 flex items-center gap-1.5">
                <span>⚡ Ultra 4K Download Pipeline</span>
              </h4>
              <p class="text-xs text-slate-600 dark:text-slate-400">
                Powered by a multi-threaded Python engine paired with <strong>FFmpeg 9.0</strong> remuxing. It streams pristine 4K/2K/1080p video and studio-grade 320kbps MP3 audio seamlessly.
              </p>
            </div>

            <div class="p-4 rounded-2xl bg-purple-500/10 border border-purple-500/20">
              <h4 class="font-bold text-purple-700 dark:text-purple-300 text-sm mb-1 flex items-center gap-1.5">
                <span>🧠 Zero-Media AI Transcription</span>
              </h4>
              <p class="text-xs text-slate-600 dark:text-slate-400">
                Extracts authentic spoken dialogue in <strong>1 to 2 seconds</strong> without downloading gigabytes of video chunks, converting raw subtitle cues into clean, readable paragraphs.
              </p>
            </div>
          </div>

          <div class="p-4 rounded-2xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
            <h4 class="font-bold text-slate-900 dark:text-white text-sm mb-1.5">🛡️ Zero Rate-Limit Immunity</h4>
            <p class="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Equipped with deep <strong>curl_cffi</strong> browser TLS impersonation. YouTube servers see standard web browser handshakes, permanently eliminating "429 Too Many Requests" and IP ban roadblocks.
            </p>
          </div>
        </div>
      `
    },

    faq: {
      title: "Frequently Asked Questions",
      subtitle: "Help Center & Operating Guide",
      icon: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`,
      content: `
        <div class="space-y-3">
          <div class="p-4 rounded-2xl bg-white/70 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 shadow-sm">
            <h4 class="font-bold text-slate-900 dark:text-white text-sm mb-1">1. How do I download 4K or 1080p videos with audio?</h4>
            <p class="text-xs text-slate-600 dark:text-slate-400">
              Paste the YouTube link, click <strong>"Download Video"</strong>, and choose your preferred resolution badge (e.g. 4K, 2K, 1080p). The server downloads the highest quality visual and audio tracks, merges them cleanly into a pristine MP4 file, and automatically triggers your browser download.
            </p>
          </div>

          <div class="p-4 rounded-2xl bg-white/70 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 shadow-sm">
            <h4 class="font-bold text-slate-900 dark:text-white text-sm mb-1">2. How does Transcript Generation work so quickly?</h4>
            <p class="text-xs text-slate-600 dark:text-slate-400">
              Unlike traditional downloaders that download the full video file, our engine requests only the lightweight caption manifests directly. It parses VTT cues into clean prose in under 2 seconds.
            </p>
          </div>

          <div class="p-4 rounded-2xl bg-white/70 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 shadow-sm">
            <h4 class="font-bold text-slate-900 dark:text-white text-sm mb-1">3. Can I translate transcripts into other languages?</h4>
            <p class="text-xs text-slate-600 dark:text-slate-400">
              Yes! Inside the Transcript pop-up modal, simply select any language from the dropdown (Urdu, Hindi, Arabic, Spanish, French, German, Chinese, etc.). The transcript instantly updates with high-accuracy translation.
            </p>
          </div>

          <div class="p-4 rounded-2xl bg-white/70 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 shadow-sm">
            <h4 class="font-bold text-slate-900 dark:text-white text-sm mb-1">4. Can I use this service on mobile devices and tablets?</h4>
            <p class="text-xs text-slate-600 dark:text-slate-400">
              Yes! YTCache Studio is fully responsive and cross-platform. It works seamlessly across smartphones, tablets, laptops, and desktop computers with zero installation required.
            </p>
          </div>
        </div>
      `
    },

    privacy: {
      title: "Privacy & Data Policy",
      subtitle: "Commitment to Zero-Log Data Protection",
      icon: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>`,
      content: `
        <div class="space-y-4">
          <p class="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            At YTCache Studio, privacy is fundamental. We designed our architecture around complete data minimization and ephemeral processing.
          </p>

          <div class="space-y-3">
            <div class="flex items-start gap-3 p-3.5 rounded-2xl bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
              <span class="text-emerald-500 font-black text-base">✓</span>
              <div>
                <h5 class="text-xs font-bold text-slate-900 dark:text-white">Zero Personal Data Collection</h5>
                <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">We do not require user accounts, email registration, credit cards, or tracking cookies.</p>
              </div>
            </div>

            <div class="flex items-start gap-3 p-3.5 rounded-2xl bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
              <span class="text-emerald-500 font-black text-base">✓</span>
              <div>
                <h5 class="text-xs font-bold text-slate-900 dark:text-white">Automatic 1-Hour File Purge</h5>
                <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">Any downloaded media is automatically and permanently purged from server disk after 60 minutes.</p>
              </div>
            </div>

            <div class="flex items-start gap-3 p-3.5 rounded-2xl bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
              <span class="text-emerald-500 font-black text-base">✓</span>
              <div>
                <h5 class="text-xs font-bold text-slate-900 dark:text-white">No Search Query Retention</h5>
                <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">URLs entered into the input box are processed on-the-fly and never stored or logged into persistent analytics.</p>
              </div>
            </div>
          </div>
        </div>
      `
    },

    terms: {
      title: "Terms & Conditions",
      subtitle: "Fair Usage & Legal Notice",
      icon: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>`,
      content: `
        <div class="space-y-4 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
          <p>
            By accessing or utilizing <strong>YTCache Studio Pro</strong>, you agree to comply with the terms and conditions outlined below:
          </p>

          <div class="space-y-2.5">
            <h5 class="font-bold text-slate-900 dark:text-white text-xs">1. Permitted Personal &amp; Educational Use</h5>
            <p class="text-xs text-slate-500 dark:text-slate-400">
              This service is provided strictly for personal archival, academic research, and non-commercial educational purposes. Users are responsible for ensuring compliance with copyright laws in their respective jurisdictions.
            </p>

            <h5 class="font-bold text-slate-900 dark:text-white text-xs mt-3">2. Intellectual Property Rights</h5>
            <p class="text-xs text-slate-500 dark:text-slate-400">
              All video titles, audio tracks, and trademarks belong to their respective creators and copyright owners. YTCache Studio does not claim ownership over any third-party content accessed via the service.
            </p>

            <h5 class="font-bold text-slate-900 dark:text-white text-xs mt-3">3. Prohibition of Commercial Resale</h5>
            <p class="text-xs text-slate-500 dark:text-slate-400">
              You may not resell, redistribute, or build automated unauthorized scraping systems against the platform APIs.
            </p>
          </div>
        </div>
      `
    },

    contact: {
      title: "Contact Us & Developer Support",
      subtitle: "Inquiries, Bug Reports & Feature Requests",
      icon: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>`,
      content: `
        <div class="space-y-4">
          <p class="text-xs sm:text-sm text-slate-600 dark:text-slate-300">
            Have questions, need technical support, or want to suggest a new feature? Fill out the form below to reach the core development team directly.
          </p>

          <form id="contact-form" class="space-y-3 mt-2">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Your Name</label>
                <input type="text" id="contact-name" required placeholder="John Doe" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500">
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Your Email</label>
                <input type="email" id="contact-email" required placeholder="john@example.com" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500">
              </div>
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Subject</label>
              <select id="contact-subject" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500">
                <option value="general">General Inquiry</option>
                <option value="bug">Bug Report / Download Issue</option>
                <option value="feature">New Feature Suggestion</option>
                <option value="feedback">Product Feedback</option>
              </select>
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Message</label>
              <textarea id="contact-message" required rows="3" placeholder="Tell us how we can help you..." class="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500"></textarea>
            </div>

            <div id="contact-alert" class="hidden p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs font-bold text-center">
              Thank you! Your message has been received. Our team will get back to you shortly.
            </div>

            <button type="submit" id="contact-submit-btn" class="btn-ripple w-full py-3 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 transition shadow-md shadow-indigo-600/25 cursor-pointer">
              Send Message
            </button>
          </form>
        </div>
      `
    }
  };

  // Smooth Animated Modal Opening
  function openInfoModal(pageKey) {
    const page = pagesData[pageKey];
    if (!page || !infoModal) return;

    if (infoModalTitle) infoModalTitle.textContent = page.title;
    if (infoModalSubtitle) infoModalSubtitle.textContent = page.subtitle;
    if (infoModalIconContainer) infoModalIconContainer.innerHTML = page.icon;
    if (infoModalContent) infoModalContent.innerHTML = page.content;

    if (pageKey === 'contact') {
      const form = document.getElementById('contact-form');
      if (form) {
        form.addEventListener('submit', (e) => {
          e.preventDefault();
          const alertBox = document.getElementById('contact-alert');
          const submitBtn = document.getElementById('contact-submit-btn');
          if (alertBox) alertBox.classList.remove('hidden');
          if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Message Sent ✓';
            submitBtn.classList.replace('bg-indigo-600', 'bg-emerald-600');
          }
        });
      }
    }

    // Smooth entrance transition
    infoModal.classList.remove('hidden');
    document.body.classList.add('overflow-hidden');

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        infoModal.classList.remove('opacity-0');
        infoModal.classList.add('opacity-100');
        if (infoModalCard) {
          infoModalCard.classList.remove('scale-95', 'translate-y-4', 'opacity-0');
          infoModalCard.classList.add('scale-100', 'translate-y-0', 'opacity-100');
        }
      });
    });
  }

  // Smooth Animated Modal Closing
  function closeInfoModal() {
    if (!infoModal) return;

    infoModal.classList.remove('opacity-100');
    infoModal.classList.add('opacity-0');
    if (infoModalCard) {
      infoModalCard.classList.remove('scale-100', 'translate-y-0', 'opacity-100');
      infoModalCard.classList.add('scale-95', 'translate-y-4', 'opacity-0');
    }

    setTimeout(() => {
      infoModal.classList.add('hidden');
      document.body.classList.remove('overflow-hidden');
    }, 300);
  }

  if (closeInfoModalBtn) closeInfoModalBtn.addEventListener('click', closeInfoModal);
  if (infoModalDoneBtn) infoModalDoneBtn.addEventListener('click', closeInfoModal);
  if (infoModal) {
    infoModal.addEventListener('click', (e) => {
      if (e.target === infoModal) closeInfoModal();
    });
  }

  // Handle Sidebar Navigation Links click with smooth transition
  document.querySelectorAll('#sidebar-nav button[data-page]').forEach(btn => {
    btn.addEventListener('click', () => {
      const pageKey = btn.getAttribute('data-page');
      closeSidebar();

      if (pageKey === 'home') {
        window.scrollTo({ top: 0, behavior: 'smooth' });
        if (videoUrlInput) videoUrlInput.focus();
      } else {
        // Wait for sidebar to glide out, then seamlessly fade and slide in the page modal
        setTimeout(() => {
          openInfoModal(pageKey);
        }, 220);
      }
    });
  });

  // Global Escape key handler
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (isSidebarOpen) closeSidebar();
      else if (infoModal && !infoModal.classList.contains('hidden')) closeInfoModal();
      else if (transcriptModal && !transcriptModal.classList.contains('hidden')) closeTranscriptModal();
      else if (downloaderSection && !downloaderSection.classList.contains('hidden')) closeDownloaderSection();
    }
  });

  // -------------------------------------------------------------
  // 5. DOM Elements (Dashboard)
  // -------------------------------------------------------------
  const videoUrlInput = document.getElementById('video-url');
  const pasteBtn = document.getElementById('paste-btn');
  const pasteBtnText = document.getElementById('paste-btn-text');
  const btnDownloadVideo = document.getElementById('btn-download-video');
  const btnGenerateTranscript = document.getElementById('btn-generate-transcript');
  const downloadBtnSpinner = document.getElementById('download-btn-spinner');
  const transcriptBtnSpinner = document.getElementById('transcript-btn-spinner');

  const errorBox = document.getElementById('error-box');
  const errorMessage = document.getElementById('error-message');
  const errorClose = document.getElementById('error-close');

  // Downloader Section Elements
  const downloaderSection = document.getElementById('downloader-section');
  const closeDownloaderBtn = document.getElementById('close-downloader-btn');
  const dlCardThumbnail = document.getElementById('dl-card-thumbnail');
  const dlCardTitle = document.getElementById('dl-card-title');
  const dlCardUploader = document.getElementById('dl-card-uploader');
  const dlCardDuration = document.getElementById('dl-card-duration');
  const dlCardViews = document.getElementById('dl-card-views');

  const tabVideo = document.getElementById('tab-video');
  const tabVideoOnly = document.getElementById('tab-video-only');
  const tabAudio = document.getElementById('tab-audio');

  const videoFormatsContainer = document.getElementById('video-formats-container');
  const videoOnlyFormatsContainer = document.getElementById('video-only-formats-container');
  const audioFormatsContainer = document.getElementById('audio-formats-container');

  const progressCard = document.getElementById('progress-card');
  const progressStatusText = document.getElementById('progress-status-text');
  const progressPercent = document.getElementById('progress-percent');
  const progressBarFill = document.getElementById('progress-bar-fill');
  const progressDetails = document.getElementById('progress-details');
  const progressSpeed = document.getElementById('progress-speed');
  const progressEta = document.getElementById('progress-eta');
  const downloadReadyBox = document.getElementById('download-ready-box');
  const downloadDirectLink = document.getElementById('download-direct-link');

  // Modal Elements (Transcript)
  const transcriptModal = document.getElementById('transcript-modal');
  const transcriptModalCard = document.getElementById('transcript-modal-card');
  const closeTranscriptModalBtn = document.getElementById('close-transcript-modal');
  const transcriptLangBadge = document.getElementById('transcript-lang-badge');
  const transcriptVideoTitle = document.getElementById('transcript-video-title');
  const transcriptLangSelect = document.getElementById('transcript-lang-select');
  const copyTranscriptBtn = document.getElementById('copy-transcript-btn');
  const copyBtnText = document.getElementById('copy-btn-text');
  const downloadTxtBtn = document.getElementById('download-txt-btn');

  const transcriptLoading = document.getElementById('transcript-loading');
  const transcriptLoadingText = document.getElementById('transcript-loading-text');
  const transcriptParagraphBox = document.getElementById('transcript-paragraph-box');
  const transcriptParagraph = document.getElementById('transcript-paragraph');
  const transcriptError = document.getElementById('transcript-error');
  const transcriptErrorMsg = document.getElementById('transcript-error-msg');

  // -------------------------------------------------------------
  // 6. Utility & Error Helpers
  // -------------------------------------------------------------
  function showError(msg) {
    if (errorMessage && errorBox) {
      errorMessage.textContent = msg || "An error occurred while communicating with the server.";
      errorBox.classList.remove('hidden');
      errorBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  function hideError() {
    if (errorBox) {
      errorBox.classList.add('hidden');
    }
  }

  if (errorClose) {
    errorClose.addEventListener('click', hideError);
  }

  function getBadgeClass(badge) {
    switch ((badge || '').toUpperCase()) {
      case '4K': return 'badge-4k';
      case '2K': return 'badge-2k';
      case 'FHD':
      case '1080P': return 'badge-fhd';
      case 'HD':
      case '720P': return 'badge-hd';
      default: return 'badge-sd';
    }
  }

  // -------------------------------------------------------------
  // 7. Fully Functional Paste Button with Direct Feedback
  // -------------------------------------------------------------
  if (pasteBtn && videoUrlInput) {
    pasteBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      hideError();

      const originalBtnText = pasteBtnText ? pasteBtnText.textContent : 'Paste';

      // Method 1: Modern Async Clipboard API
      try {
        if (navigator.clipboard && navigator.clipboard.readText) {
          const clipText = await navigator.clipboard.readText();
          if (clipText && clipText.trim()) {
            videoUrlInput.value = clipText.trim();
            videoUrlInput.dispatchEvent(new Event('input', { bubbles: true }));
            videoUrlInput.dispatchEvent(new Event('change', { bubbles: true }));
            videoUrlInput.focus();

            if (pasteBtnText) pasteBtnText.textContent = 'Pasted! ✓';
            pasteBtn.classList.add('border-emerald-500', 'text-emerald-600', 'dark:text-emerald-400');
            setTimeout(() => {
              if (pasteBtnText) pasteBtnText.textContent = originalBtnText;
              pasteBtn.classList.remove('border-emerald-500', 'text-emerald-600', 'dark:text-emerald-400');
            }, 1800);
            return;
          }
        }
      } catch (err) {
        console.warn("navigator.clipboard.readText access restricted:", err);
      }

      // Method 2: Document execCommand fallback
      videoUrlInput.focus();
      videoUrlInput.select();
      try {
        const successful = document.execCommand('paste');
        if (successful && videoUrlInput.value.trim()) {
          videoUrlInput.dispatchEvent(new Event('input', { bubbles: true }));
          if (pasteBtnText) pasteBtnText.textContent = 'Pasted! ✓';
          setTimeout(() => {
            if (pasteBtnText) pasteBtnText.textContent = originalBtnText;
          }, 1800);
          return;
        }
      } catch (err) {
        // Fallback for strict browser security policies
        const manualInput = window.prompt("Paste your YouTube link below (Ctrl+V):", videoUrlInput.value || "");
        if (manualInput && manualInput.trim()) {
          videoUrlInput.value = manualInput.trim();
          videoUrlInput.dispatchEvent(new Event('input', { bubbles: true }));
          if (pasteBtnText) pasteBtnText.textContent = 'Pasted! ✓';
          setTimeout(() => {
            if (pasteBtnText) pasteBtnText.textContent = originalBtnText;
          }, 1800);
        }
      }
    });
  }

  // -------------------------------------------------------------
  // 8. Feature 1: Video Downloader Engine
  // -------------------------------------------------------------

  async function handleDownloadVideoClick() {
    hideError();
    const url = videoUrlInput.value.trim();
    if (!url) {
      showError("Please enter a valid YouTube video URL first.");
      return;
    }

    currentVideoUrl = url;

    if (btnDownloadVideo) btnDownloadVideo.disabled = true;
    if (downloadBtnSpinner) downloadBtnSpinner.classList.remove('hidden');

    try {
      const resp = await fetch('/api/fetch-info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url })
      });

      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || data.error || "Unable to retrieve video information.");
      }

      currentVideoData = data;
      renderDownloaderSection(data);
      openDownloaderSection();

    } catch (err) {
      console.error("Downloader Error:", err);
      showError(err.message);
    } finally {
      if (btnDownloadVideo) btnDownloadVideo.disabled = false;
      if (downloadBtnSpinner) downloadBtnSpinner.classList.add('hidden');
    }
  }

  function openDownloaderSection() {
    if (!downloaderSection) return;
    downloaderSection.classList.remove('hidden');
    downloaderSection.classList.add('opacity-0', 'translate-y-4');
    downloaderSection.classList.remove('opacity-100', 'translate-y-0');

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        downloaderSection.classList.remove('opacity-0', 'translate-y-4');
        downloaderSection.classList.add('opacity-100', 'translate-y-0');
        downloaderSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  function closeDownloaderSection() {
    if (!downloaderSection || downloaderSection.classList.contains('hidden')) return;

    downloaderSection.classList.add('opacity-0', '-translate-y-3');
    downloaderSection.classList.remove('opacity-100', 'translate-y-0');

    const heroTarget = document.getElementById('hero-input-panel') || document.getElementById('video-url') || document.body;
    heroTarget.scrollIntoView({ behavior: 'smooth', block: 'center' });

    setTimeout(() => {
      downloaderSection.classList.add('hidden');
      downloaderSection.classList.remove('opacity-0', '-translate-y-3');
    }, 300);
  }

  if (btnDownloadVideo) {
    btnDownloadVideo.addEventListener('click', handleDownloadVideoClick);
  }

  if (closeDownloaderBtn) {
    closeDownloaderBtn.addEventListener('click', closeDownloaderSection);
  }

  function renderDownloaderSection(data) {
    if (dlCardThumbnail) dlCardThumbnail.src = data.thumbnail || '';
    if (dlCardTitle) dlCardTitle.textContent = data.title || 'YouTube Video';
    if (dlCardUploader) dlCardUploader.textContent = data.uploader || 'Creator';
    if (dlCardDuration) dlCardDuration.textContent = data.duration_formatted || '00:00';
    if (dlCardViews) dlCardViews.textContent = data.view_count || '0';

    // Video with Sound
    renderFormatList(videoFormatsContainer, data.video_formats || [], 'video');

    // Visuals Only
    renderFormatList(videoOnlyFormatsContainer, data.video_only_formats || [], 'video_only');

    // Audio Only
    renderAudioFormatList(audioFormatsContainer, data.audio_formats || []);
  }

  function renderFormatList(container, formats, downloadType) {
    if (!container) return;
    container.innerHTML = '';

    if (!formats || formats.length === 0) {
      container.innerHTML = `<div class="col-span-full p-6 text-center text-xs text-slate-500 font-semibold">No formats available for this category.</div>`;
      return;
    }

    formats.forEach(f => {
      const card = document.createElement('div');
      card.className = "glass-panel rounded-2xl p-4 flex items-center justify-between gap-3.5 hover:border-indigo-500/50 transition shadow-sm";

      const badgeStyle = getBadgeClass(f.badge);

      card.innerHTML = `
        <div class="flex items-center gap-3.5 min-w-0">
          <span class="px-2.5 py-1 rounded-xl text-xs font-black shadow-sm flex-shrink-0 ${badgeStyle}">
            ${f.resolution}
          </span>
          <div class="min-w-0">
            <div class="text-sm font-extrabold text-slate-900 dark:text-white leading-tight truncate">${f.name}</div>
            <div class="text-xs text-slate-600 dark:text-slate-400 mt-0.5 font-semibold">MP4 &bull; ${f.fps} FPS &bull; <span class="font-bold text-slate-900 dark:text-slate-200">${f.estimated_size}</span></div>
          </div>
        </div>
        <button type="button" class="btn-ripple btn-start-dl px-4 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 active:scale-95 transition flex items-center gap-1.5 shadow-md shadow-indigo-600/25 cursor-pointer flex-shrink-0" data-height="${f.height || ''}" data-type="${downloadType}">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
          <span>Download</span>
        </button>
      `;

      container.appendChild(card);
    });

    container.querySelectorAll('.btn-start-dl').forEach(btn => {
      btn.addEventListener('click', () => {
        const height = btn.getAttribute('data-height');
        const type = btn.getAttribute('data-type');
        triggerDownload(type, height ? parseInt(height) : null, null);
      });
    });
  }

  function renderAudioFormatList(container, formats) {
    if (!container) return;
    container.innerHTML = '';

    if (!formats || formats.length === 0) {
      container.innerHTML = `<div class="col-span-full p-6 text-center text-xs text-slate-500 font-semibold">No audio formats available.</div>`;
      return;
    }

    formats.forEach(f => {
      const card = document.createElement('div');
      card.className = "glass-panel rounded-2xl p-4 flex items-center justify-between gap-3.5 hover:border-indigo-500/50 transition shadow-sm";

      card.innerHTML = `
        <div class="flex items-center gap-3.5 min-w-0">
          <span class="px-2.5 py-1 rounded-xl text-xs font-black shadow-sm bg-gradient-to-r from-amber-500 to-rose-600 text-white flex-shrink-0">
            ${(f.ext || 'audio').toUpperCase()}
          </span>
          <div class="min-w-0">
            <div class="text-sm font-extrabold text-slate-900 dark:text-white leading-tight truncate">${f.name}</div>
            <div class="text-xs text-slate-600 dark:text-slate-400 mt-0.5 font-semibold">${f.quality} &bull; <span class="font-bold text-slate-900 dark:text-slate-200">${f.estimated_size}</span></div>
          </div>
        </div>
        <button type="button" class="btn-ripple btn-start-audio-dl px-4 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 active:scale-95 transition flex items-center gap-1.5 shadow-md shadow-indigo-600/25 cursor-pointer flex-shrink-0" data-format="${f.format_id}">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
          <span>Download</span>
        </button>
      `;

      container.appendChild(card);
    });

    container.querySelectorAll('.btn-start-audio-dl').forEach(btn => {
      btn.addEventListener('click', () => {
        const formatId = btn.getAttribute('data-format');
        triggerDownload('audio', null, formatId);
      });
    });
  }

  // Tabs Switching Logic
  const activeTabClass = "btn-ripple px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-indigo-600 text-white shadow-md shadow-indigo-600/25 cursor-pointer";
  const inactiveTabClass = "btn-ripple btn-light-ripple px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 text-slate-700 dark:text-slate-400 bg-slate-200/80 dark:bg-slate-800/80 hover:bg-slate-300 dark:hover:bg-slate-700 cursor-pointer";

  if (tabVideo) {
    tabVideo.addEventListener('click', () => {
      tabVideo.className = activeTabClass;
      if (tabVideoOnly) tabVideoOnly.className = inactiveTabClass;
      if (tabAudio) tabAudio.className = inactiveTabClass;
      if (videoFormatsContainer) videoFormatsContainer.classList.remove('hidden');
      if (videoOnlyFormatsContainer) videoOnlyFormatsContainer.classList.add('hidden');
      if (audioFormatsContainer) audioFormatsContainer.classList.add('hidden');
    });
  }

  if (tabVideoOnly) {
    tabVideoOnly.addEventListener('click', () => {
      tabVideoOnly.className = activeTabClass;
      if (tabVideo) tabVideo.className = inactiveTabClass;
      if (tabAudio) tabAudio.className = inactiveTabClass;
      if (videoOnlyFormatsContainer) videoOnlyFormatsContainer.classList.remove('hidden');
      if (videoFormatsContainer) videoFormatsContainer.classList.add('hidden');
      if (audioFormatsContainer) audioFormatsContainer.classList.add('hidden');
    });
  }

  if (tabAudio) {
    tabAudio.addEventListener('click', () => {
      tabAudio.className = activeTabClass;
      if (tabVideo) tabVideo.className = inactiveTabClass;
      if (tabVideoOnly) tabVideoOnly.className = inactiveTabClass;
      if (audioFormatsContainer) audioFormatsContainer.classList.remove('hidden');
      if (videoFormatsContainer) videoFormatsContainer.classList.add('hidden');
      if (videoOnlyFormatsContainer) videoOnlyFormatsContainer.classList.add('hidden');
    });
  }

  // Download Trigger & Progress Poller
  async function triggerDownload(type, height, audioFormat) {
    hideError();
    if (!currentVideoUrl) {
      currentVideoUrl = videoUrlInput.value.trim();
    }
    if (!currentVideoUrl) return;

    if (progressCard) {
      progressCard.classList.remove('hidden');
      progressCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    if (downloadReadyBox) downloadReadyBox.classList.add('hidden');

    if (progressStatusText) progressStatusText.textContent = "Connecting to YouTube servers...";
    if (progressPercent) progressPercent.textContent = "0%";
    if (progressBarFill) progressBarFill.style.width = "0%";
    if (progressDetails) progressDetails.textContent = "Initializing pipeline...";
    if (progressSpeed) progressSpeed.textContent = "";
    if (progressEta) progressEta.textContent = "";

    try {
      const resp = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: currentVideoUrl,
          type: type,
          height: height,
          audio_format: audioFormat
        })
      });

      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || "Failed to initialize download pipeline.");
      }

      const jobId = data.job_id;
      startPollingProgress(jobId);

    } catch (err) {
      console.error("Download Task Error:", err);
      showError(err.message);
      if (progressCard) progressCard.classList.add('hidden');
    }
  }

  function startPollingProgress(jobId) {
    if (activePollInterval) clearInterval(activePollInterval);

    activePollInterval = setInterval(async () => {
      try {
        const resp = await fetch(`/api/progress/${jobId}`);
        const data = await resp.json();

        if (!resp.ok) {
          clearInterval(activePollInterval);
          showError(data.detail || "Unable to monitor download progress.");
          return;
        }

        const pct = Math.min(Math.round(data.percent || 0), 100);
        if (progressPercent) progressPercent.textContent = `${pct}%`;
        if (progressBarFill) progressBarFill.style.width = `${pct}%`;
        if (progressStatusText) progressStatusText.textContent = data.message || "Downloading...";

        if (progressDetails) {
          if (data.downloaded && data.total) {
            progressDetails.textContent = `${data.downloaded} / ${data.total}`;
          } else {
            progressDetails.textContent = data.message || "";
          }
        }

        if (progressSpeed) progressSpeed.textContent = data.speed ? `Speed: ${data.speed}` : '';
        if (progressEta) progressEta.textContent = data.eta ? `ETA: ${data.eta}` : '';

        if (data.status === 'completed') {
          clearInterval(activePollInterval);
          if (progressBarFill) progressBarFill.style.width = "100%";
          if (progressPercent) progressPercent.textContent = "100%";
          if (progressStatusText) progressStatusText.textContent = "Download Complete!";

          const streamUrl = data.download_url || `/api/stream/${jobId}`;
          if (downloadDirectLink) {
            downloadDirectLink.href = streamUrl;
            downloadDirectLink.setAttribute('download', data.file_name || 'download');
          }
          if (downloadReadyBox) downloadReadyBox.classList.remove('hidden');

          const tempAnchor = document.createElement('a');
          tempAnchor.href = streamUrl;
          tempAnchor.setAttribute('download', data.file_name || 'download');
          document.body.appendChild(tempAnchor);
          tempAnchor.click();
          document.body.removeChild(tempAnchor);

        } else if (data.status === 'error') {
          clearInterval(activePollInterval);
          showError(data.error || "An error occurred during video processing.");
        }

      } catch (err) {
        console.error("Progress Poll Error:", err);
      }
    }, 800);
  }

  // -------------------------------------------------------------
  // 9. Feature 2: Fast Authentic Speech Transcript & Translator (Smooth Transition)
  // -------------------------------------------------------------

  function openTranscriptModal() {
    if (!transcriptModal) return;

    transcriptModal.classList.remove('hidden');
    document.body.classList.add('overflow-hidden');

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        transcriptModal.classList.remove('opacity-0');
        transcriptModal.classList.add('opacity-100');
        if (transcriptModalCard) {
          transcriptModalCard.classList.remove('scale-95', 'translate-y-4', 'opacity-0');
          transcriptModalCard.classList.add('scale-100', 'translate-y-0', 'opacity-100');
        }
      });
    });
  }

  function closeTranscriptModal() {
    if (!transcriptModal) return;

    transcriptModal.classList.remove('opacity-100');
    transcriptModal.classList.add('opacity-0');
    if (transcriptModalCard) {
      transcriptModalCard.classList.remove('scale-100', 'translate-y-0', 'opacity-100');
      transcriptModalCard.classList.add('scale-95', 'translate-y-4', 'opacity-0');
    }

    setTimeout(() => {
      transcriptModal.classList.add('hidden');
      document.body.classList.remove('overflow-hidden');
    }, 300);
  }

  if (closeTranscriptModalBtn) {
    closeTranscriptModalBtn.addEventListener('click', closeTranscriptModal);
  }

  if (transcriptModal) {
    transcriptModal.addEventListener('click', (e) => {
      if (e.target === transcriptModal) closeTranscriptModal();
    });
  }

  function showModalLoading(text) {
    if (transcriptLoading) {
      transcriptLoading.classList.remove('hidden');
      if (transcriptLoadingText) transcriptLoadingText.textContent = text || "Extracting spoken audio transcript...";
    }
    if (transcriptParagraphBox) transcriptParagraphBox.classList.add('hidden');
    if (transcriptError) transcriptError.classList.add('hidden');
  }

  function showModalParagraph(text, langBadgeText) {
    if (transcriptLoading) transcriptLoading.classList.add('hidden');
    if (transcriptError) transcriptError.classList.add('hidden');
    if (transcriptParagraphBox && transcriptParagraph) {
      transcriptParagraph.textContent = text;
      transcriptParagraphBox.classList.remove('hidden');
    }
    if (transcriptLangBadge && langBadgeText) {
      transcriptLangBadge.textContent = langBadgeText;
    }
  }

  function showModalError(msg) {
    if (transcriptLoading) transcriptLoading.classList.add('hidden');
    if (transcriptParagraphBox) transcriptParagraphBox.classList.add('hidden');
    if (transcriptError) {
      if (transcriptErrorMsg) transcriptErrorMsg.textContent = msg || "No speech transcript available.";
      transcriptError.classList.remove('hidden');
    }
  }

  async function fetchTranscript(url, lang = "original") {
    const isInitial = (lang === "original");
    
    if (isInitial) {
      openTranscriptModal();
      showModalLoading("Extracting authentic spoken speech transcript...");
      if (transcriptLangBadge) transcriptLangBadge.textContent = "Loading...";
      if (transcriptVideoTitle) transcriptVideoTitle.textContent = "Please wait...";
    } else {
      showModalLoading(`Translating speech transcript to ${lang}...`);
      if (transcriptLangSelect) transcriptLangSelect.disabled = true;
    }

    try {
      const resp = await fetch('/api/transcript', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url, lang: lang })
      });

      const data = await resp.json();

      if (!resp.ok || !data.success) {
        throw new Error(data.detail || data.error || "Failed to retrieve speech transcript.");
      }

      currentTranscriptData = data;

      if (transcriptVideoTitle) transcriptVideoTitle.textContent = data.video_title || 'YouTube Video';
      showModalParagraph(data.paragraph, data.current_lang_name);

    } catch (err) {
      console.error("Transcript Error:", err);
      showModalError(err.message);
      if (isInitial) {
        showError(err.message);
      }
    } finally {
      if (transcriptLangSelect) transcriptLangSelect.disabled = false;
    }
  }

  async function handleGenerateTranscriptClick() {
    hideError();
    const url = videoUrlInput.value.trim();
    if (!url) {
      showError("Please enter a valid YouTube video URL first.");
      return;
    }

    currentVideoUrl = url;

    if (transcriptLangSelect) transcriptLangSelect.value = "original";

    if (btnGenerateTranscript) btnGenerateTranscript.disabled = true;
    if (transcriptBtnSpinner) transcriptBtnSpinner.classList.remove('hidden');

    try {
      await fetchTranscript(url, "original");
    } finally {
      if (btnGenerateTranscript) btnGenerateTranscript.disabled = false;
      if (transcriptBtnSpinner) transcriptBtnSpinner.classList.add('hidden');
    }
  }

  if (btnGenerateTranscript) {
    btnGenerateTranscript.addEventListener('click', handleGenerateTranscriptClick);
  }

  // Language Dropdown Translation Change Listener
  if (transcriptLangSelect) {
    transcriptLangSelect.addEventListener('change', async (e) => {
      const selectedLang = e.target.value;
      if (!currentVideoUrl) {
        currentVideoUrl = videoUrlInput.value.trim();
      }
      if (!currentVideoUrl) return;

      await fetchTranscript(currentVideoUrl, selectedLang);
    });
  }

  // Single-Click Copy Action with Feedback
  if (copyTranscriptBtn) {
    copyTranscriptBtn.addEventListener('click', async () => {
      const textToCopy = transcriptParagraph ? transcriptParagraph.textContent : '';
      if (!textToCopy || !textToCopy.trim()) return;

      try {
        await navigator.clipboard.writeText(textToCopy);
        const originalText = copyBtnText ? copyBtnText.textContent : 'Copy';
        if (copyBtnText) copyBtnText.textContent = 'Copied to Clipboard! ✓';
        copyTranscriptBtn.classList.add('border-emerald-500', 'text-emerald-600', 'dark:text-emerald-400');

        setTimeout(() => {
          if (copyBtnText) copyBtnText.textContent = originalText;
          copyTranscriptBtn.classList.remove('border-emerald-500', 'text-emerald-600', 'dark:text-emerald-400');
        }, 2000);
      } catch (err) {
        console.error("Copy fallback triggered:", err);
        const tempTextarea = document.createElement('textarea');
        tempTextarea.value = textToCopy;
        document.body.appendChild(tempTextarea);
        tempTextarea.select();
        document.execCommand('copy');
        document.body.removeChild(tempTextarea);

        if (copyBtnText) copyBtnText.textContent = 'Copied to Clipboard! ✓';
        setTimeout(() => {
          if (copyBtnText) copyBtnText.textContent = 'Copy';
        }, 2000);
      }
    });
  }

  // Single-Click Download .txt Action
  if (downloadTxtBtn) {
    downloadTxtBtn.addEventListener('click', () => {
      const textToDownload = transcriptParagraph ? transcriptParagraph.textContent : '';
      if (!textToDownload || !textToDownload.trim()) return;

      const title = (currentTranscriptData && currentTranscriptData.video_title) 
        ? currentTranscriptData.video_title.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 50) 
        : 'video';
      const lang = (currentTranscriptData && currentTranscriptData.current_lang) || 'original';
      const filename = `${title}_transcript_${lang}.txt`;

      const header = `========================================================\n` +
                     `Title: ${(currentTranscriptData && currentTranscriptData.video_title) || 'YouTube Video'}\n` +
                     `Language: ${(currentTranscriptData && currentTranscriptData.current_lang_name) || lang}\n` +
                     `Generated with YTCache Studio Pro\n` +
                     `========================================================\n\n`;

      const blob = new Blob([header + textToDownload], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }

});
