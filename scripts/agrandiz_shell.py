#!/usr/bin/env python3

"""Shared app-shell helpers: nav CSS and nav HTML used by all page renderers."""

APP_NAV_CSS = """    .app-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 18px 0 0;
    }
    .app-nav a {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 8px 12px;
      background: rgba(255,255,255,.72);
      border: 1px solid rgba(0,0,0,.08);
      color: #0071e3;
      font-weight: 650;
      text-decoration: none;
    }
    .app-nav a[aria-current="page"] {
      background: rgba(0,113,227,.10);
      color: #1d1d1f;
    }"""


def app_nav_html(active=None, theme="apple", profile="apple_icloud"):
    """Return the app navigation bar HTML.

    active: 'dashboard' | 'stories' | 'family_timeline' | None
    """
    def cur(page):
        return ' aria-current="page"' if active == page else ""

    return (
        f'<nav class="app-nav" aria-label="Agrandiz">\n'
        f'        <a href="dashboard.{theme}.{profile}.html"{cur("dashboard")} data-i18n="nav.dashboard">Dashboard</a>\n'
        f'        <a href="stories.{theme}.{profile}.html"{cur("stories")} data-i18n="nav.stories">Stories</a>\n'
        f'        <a href="family-timeline.{theme}.{profile}.html"{cur("family_timeline")} data-i18n="nav.family_timeline">Family Timeline</a>\n'
        f'      </nav>'
    )
