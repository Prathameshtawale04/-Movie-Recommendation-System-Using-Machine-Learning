/**
 * MovieFlix - Frontend JavaScript
 * Netflix-Inspired Scroll-Tied UI, Parallax, IntersectionObserver Animations,
 * Carousel Scrolling, Mobile Drawer, and Defensive Image Fallbacks.
 */

document.addEventListener('DOMContentLoaded', () => {
  const FALLBACK_POSTER = '/static/img/poster-fallback.svg';

  // ----------------------------------------------------------------------------
  // 1. Defensive Image Fallback Handler
  // ----------------------------------------------------------------------------
  function attachImageFallbacks() {
    document.querySelectorAll('img').forEach((img) => {
      // Guard against /None, null, or empty src
      if (!img.src || img.src.includes('/None') || img.src.endsWith('/img/')) {
        img.src = FALLBACK_POSTER;
      }

      img.addEventListener('error', function () {
        if (this.src !== window.location.origin + FALLBACK_POSTER && !this.src.endsWith(FALLBACK_POSTER)) {
          this.src = FALLBACK_POSTER;
        }
      });
    });
  }
  attachImageFallbacks();

  // ----------------------------------------------------------------------------
  // 2. Dynamic Sticky Navigation on Scroll
  // ----------------------------------------------------------------------------
  const siteHeader = document.getElementById('siteHeader');
  if (siteHeader) {
    const handleNavScroll = () => {
      if (window.scrollY > 30) {
        siteHeader.classList.add('scrolled');
      } else {
        siteHeader.classList.remove('scrolled');
      }
    };
    window.addEventListener('scroll', handleNavScroll, { passive: true });
    handleNavScroll();
  }

  // ----------------------------------------------------------------------------
  // 3. Scroll-Tied Hero Parallax & Fade Effect
  // ----------------------------------------------------------------------------
  const heroStage = document.getElementById('heroStage');
  const heroBackdrop = document.getElementById('heroBackdrop');
  const heroContent = document.getElementById('heroContent');

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (heroStage && heroBackdrop && heroContent && !prefersReducedMotion) {
    let ticking = false;

    window.addEventListener('scroll', () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const scrollY = window.scrollY;
          const stageHeight = heroStage.offsetHeight;

          if (scrollY <= stageHeight) {
            // Subtle parallax translation of backdrop image
            const backdropOffset = scrollY * 0.32;
            heroBackdrop.style.transform = `translate3d(0, ${backdropOffset}px, 0)`;

            // Subtle fade and upward translate of hero typography
            const opacity = Math.max(0, 1 - (scrollY / (stageHeight * 0.75)));
            const textOffset = scrollY * 0.18;
            heroContent.style.opacity = opacity.toFixed(2);
            heroContent.style.transform = `translate3d(0, ${textOffset}px, 0)`;
          }

          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });
  }

  // ----------------------------------------------------------------------------
  // 4. IntersectionObserver: Scroll-Tied Section Reveals
  // ----------------------------------------------------------------------------
  const revealSections = document.querySelectorAll('.scroll-reveal-section');

  if ('IntersectionObserver' in window && !prefersReducedMotion) {
    const sectionObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in-view');
          observer.unobserve(entry.target);
        }
      });
    }, {
      root: null,
      threshold: 0.12,
      rootMargin: '0px 0px -40px 0px',
    });

    revealSections.forEach((section) => {
      sectionObserver.observe(section);
    });
  } else {
    // Fallback: immediately show all sections
    revealSections.forEach((section) => section.classList.add('in-view'));
  }

  // ----------------------------------------------------------------------------
  // 5. Horizontal Carousel Scroll Navigation
  // ----------------------------------------------------------------------------
  window.scrollTrack = function (trackId, offset) {
    const track = document.getElementById(trackId);
    if (track) {
      track.scrollBy({
        left: offset,
        behavior: 'smooth',
      });
    }
  };

  // ----------------------------------------------------------------------------
  // 6. Mobile Menu Drawer Toggle
  // ----------------------------------------------------------------------------
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');
  const mobileMenuDrawer = document.getElementById('mobileMenuDrawer');

  if (mobileMenuBtn && mobileMenuDrawer) {
    mobileMenuBtn.addEventListener('click', () => {
      mobileMenuDrawer.classList.toggle('open');
      const isOpen = mobileMenuDrawer.classList.contains('open');
      mobileMenuBtn.setAttribute('aria-expanded', isOpen);
    });
  }

  // ----------------------------------------------------------------------------
  // 7. Interactive Star Rating Hover Dynamics
  // ----------------------------------------------------------------------------
  const starForm = document.getElementById('starRatingForm');
  if (starForm) {
    const stars = starForm.querySelectorAll('.star-btn');
    stars.forEach((btn, idx) => {
      btn.addEventListener('mouseenter', () => {
        stars.forEach((s, sIdx) => {
          if (sIdx <= idx) {
            s.style.color = 'var(--accent-gold)';
          } else {
            s.style.color = 'rgba(255, 255, 255, 0.25)';
          }
        });
      });

      btn.addEventListener('mouseleave', () => {
        stars.forEach((s) => {
          s.style.color = '';
        });
      });
    });
  }

  // ----------------------------------------------------------------------------
  // 8. Auto-dismiss Flash Alerts
  // ----------------------------------------------------------------------------
  const flashContainer = document.getElementById('flashContainer');
  if (flashContainer) {
    setTimeout(() => {
      const toasts = flashContainer.querySelectorAll('.flash-toast');
      toasts.forEach((t) => {
        t.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        t.style.opacity = '0';
        t.style.transform = 'translateX(30px)';
        setTimeout(() => t.remove(), 400);
      });
    }, 5000);
  }
});
