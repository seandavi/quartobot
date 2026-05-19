// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";

// https://astro.build/config
export default defineConfig({
  site: "https://seandavi.github.io",
  base: "/quartobot",
  integrations: [
    starlight({
      title: "quartobot",
      description: "Citation resolution and manuscript-as-software CI for Quarto.",
      logo: { src: "./src/assets/logo.svg", replacesTitle: false },
      customCss: ["./src/styles/feature-bands.css"],
      // Google Analytics 4 + onboarding-event instrumentation.
      // page_view, scroll-to-90%, and outbound clicks are tracked by
      // GA4 automatically. We layer per-CTA events on top so the
      // "which onboarding step did the user take next" question is
      // answerable in reports without slicing the raw URL.
      head: [
        {
          tag: "script",
          attrs: {
            async: true,
            src: "https://www.googletagmanager.com/gtag/js?id=G-QNEGW3C1W0",
          },
        },
        {
          tag: "script",
          content: `
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', 'G-QNEGW3C1W0');

document.addEventListener('click', function (e) {
  // Code-block copy buttons (Starlight's expressive-code copy widget).
  // Install command copy is the highest-intent signal we have short of
  // an actual install — split it out from generic code copies.
  var copyBtn = e.target.closest('button[data-code]');
  if (copyBtn) {
    var code = (copyBtn.getAttribute('data-code') || '').slice(0, 120);
    if (/uv tool install quartobot/.test(code)) {
      gtag('event', 'install_command_copy', { code: code });
    } else {
      gtag('event', 'code_copy', { code: code });
    }
    return;
  }

  var a = e.target.closest('a[href]');
  if (!a) return;
  var href = a.getAttribute('href') || '';
  var text = (a.textContent || '').trim().slice(0, 80);

  // Hero action buttons (the splash-template frontmatter actions).
  if (a.closest('.hero .actions')) {
    gtag('event', 'hero_cta_click', { link_text: text, link_url: href });
    return;
  }

  // Layer feature-band CTAs (Layer 1-4 on the landing).
  if (a.closest('.feature-band__cta')) {
    var band = a.closest('.feature-band');
    var layerEl = band && band.querySelector('.feature-band__layer');
    gtag('event', 'layer_cta_click', {
      layer: layerEl ? layerEl.textContent.trim() : '',
      link_text: text,
      link_url: href,
    });
    return;
  }

  // CardGrid cards (the "Where to go next" tiles on the landing and
  // similar grids on other pages). The whole <a> carries class="card".
  if (a.classList.contains('card')) {
    var titleEl = a.querySelector('h2, h3');
    gtag('event', 'card_click', {
      card_title: titleEl ? titleEl.textContent.trim() : text,
      link_url: href,
    });
    return;
  }
}, true);

// Append a "Report an issue" link next to Starlight's "Edit page"
// link in the per-page footer. Pre-fills the issue title with the
// page title and the body with the page URL so the reporter doesn't
// have to type those.
document.addEventListener('DOMContentLoaded', function () {
  var editLink = document.querySelector(
    'footer .meta a[href*="/edit/main/"]'
  );
  if (!editLink) return;
  var pageTitle = (document.title || '').replace(/ \\| quartobot.*$/, '');
  var pageUrl = window.location.href.split('#')[0];
  var issueUrl =
    'https://github.com/seandavi/quartobot/issues/new'
    + '?title=' + encodeURIComponent('Docs: ' + pageTitle)
    + '&body=' + encodeURIComponent('Page: ' + pageUrl + String.fromCharCode(10) + String.fromCharCode(10));
  var report = document.createElement('a');
  report.href = issueUrl;
  report.className = editLink.className;
  report.target = '_blank';
  report.rel = 'noopener';
  // Tiny inline SVG so the link visually matches "Edit page" style.
  report.innerHTML =
    '<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24"'
    + ' fill="currentColor" style="--sl-icon-size: 1.2em; margin-right: 0.3em;">'
    + '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2'
    + ' 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>Report an issue';
  editLink.parentNode.appendChild(report);
});
`.trim(),
        },
      ],
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/seandavi/quartobot",
        },
      ],
      editLink: {
        baseUrl: "https://github.com/seandavi/quartobot/edit/main/site/",
      },
      // Sidebar: Install is the first thing a new user needs, so it
      // sits at the top alongside Home. Everything below is grouped by
      // Diataxis quadrant — Tutorials (learning), How-to guides
      // (doing), Reference (information), Explanation (understanding).
      sidebar: [
        { label: "Home", link: "/" },
        { label: "Install", link: "/install/" },
        { label: "Coming from…", link: "/coming-from/" },
        {
          label: "Tutorials",
          items: [
            { label: "First manuscript (15 min)", link: "/first-manuscript/" },
            { label: "MCP + Claude Desktop", link: "/mcp-claude-desktop/" },
            { label: "Shell-tool agent", link: "/shell-tool-agent/" },
          ],
        },
        {
          label: "How-to guides",
          items: [
            { label: "Choose a path in", link: "/getting-started/" },
            { label: "Resolve a single citation", link: "/resolve-single-citation/" },
            { label: "Use a Quarto website", link: "/quarto-websites/" },
            { label: "Use a Quarto book", link: "/quarto-books/" },
            { label: "Use Jupyter notebooks", link: "/jupyter-notebooks/" },
            { label: "MCP server", link: "/mcp/" },
            { label: "Migrate from manubot", link: "/migrating-from-manubot/" },
            { label: "Validate a manuscript", link: "/validate-manuscript/" },
            { label: "Troubleshooting", link: "/troubleshooting/" },
          ],
        },
        {
          label: "Reference",
          items: [
            { label: "CLI", link: "/cli/" },
          ],
        },
        {
          label: "Explanation",
          items: [
            { label: "Design", link: "/design/" },
            { label: "Differences from manubot", link: "/differences-from-manubot/" },
          ],
        },
      ],
    }),
  ],
});
