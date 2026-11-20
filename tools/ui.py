"""shadcn/ui component markup for the static Pacta site.

Every helper renders the anatomy shadcn/ui v4 renders (data-slot / data-variant / data-size attributes on the same element
structure), so docs/styles.css can style the components exactly as the React components would be styled, while the pages
stay static HTML (no runtime, no bundle). Icons are inline Lucide paths (no icon font, no third-party request).
"""
import html

E = html.escape

# Lucide icon paths (ISC licence), 24x24, stroke=currentColor
_ICONS = {
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "copy": '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "sun": ('<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/>'
            '<path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/>'
            '<path d="m19.07 4.93-1.41 1.41"/>'),
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "monitor": '<rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
    "menu": '<path d="M4 12h16"/><path d="M4 6h16"/><path d="M4 18h16"/>',
    "github": ('<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 '
               '0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 '
               '1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>'),
    # X (formerly Twitter) logo, filled (render with cls="i-fill")
    "x-logo": '<path d="M18.901 1.153h3.68l-8.04 9.19L24 22.846 h-7.406 l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    # v4.4 (R-V4): one-path forms of Lucide arrow-right / arrow-up-right for inline link markers (U.arrow)
    "arr-right": '<path d="M5 12h14M12 5l7 7-7 7"/>',
    "arr-up-right": '<path d="M7 7h10v10M7 17 17 7"/>',
    "circle-check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "external": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    "scale": '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
}


def icon(name, cls=""):
    """Lucide icon; stroke, size and caps come from the .i rule in styles.css (keeps the markup small)."""
    return f'<svg class="i{" " + cls if cls else ""}" viewBox="0 0 24 24" aria-hidden="true">{_ICONS[name]}</svg>'   # v4.6: no IE-era focusable="false" (page budget)


def arrow(kind="right"):
    """v4.4 (R-V4): inline Lucide arrow for link markers instead of a raw → / ↗ glyph (the self-hosted Inter subset has no arrows,
    so a raw glyph renders as a missing-glyph box wherever the OS has no fallback font). Decorative: aria-hidden; the link text
    carries the meaning. kind: "right" (internal link) or "up-right" (external, opens in a new tab)."""
    return f'<svg class="i ia" viewBox="0 0 24 24" aria-hidden="true">{_ICONS["arr-up-right" if kind == "up-right" else "arr-right"]}</svg>'


def _attrs(attrs):
    return (" " + attrs.strip()) if attrs and attrs.strip() else ""


def button(label_html, href=None, variant="outline", size=None, attrs="", type_="button", cls=""):
    """shadcn Button: <button data-slot="button" data-variant data-size> (asChild <a> when href is given)."""
    data = f' data-slot="button" data-variant="{variant}"' + (f' data-size="{size}"' if size else "")
    c = f' class="{cls}"' if cls else ""
    if href is not None:
        return f'<a{c}{data} href="{E(href)}"{_attrs(attrs)}>{label_html}</a>'
    return f'<button{c}{data} type="{type_}"{_attrs(attrs)}>{label_html}</button>'


def badge(text_html, variant="neutral", attrs="", cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<span{c} data-slot="badge" data-variant="{variant}"{_attrs(attrs)}>{text_html}</span>'


def card(inner, cls="", attrs="", tag="div"):
    c = f' class="{cls}"' if cls else ""
    return f'<{tag}{c} data-slot="card"{_attrs(attrs)}>{inner}</{tag}>'


def card_header(title_html, desc_html="", title_tag="h3", action_html=""):
    return (f'<div data-slot="card-header"><{title_tag} data-slot="card-title">{title_html}</{title_tag}>'
            + (f'<p data-slot="card-description">{desc_html}</p>' if desc_html else "")
            + (f'<div data-slot="card-action">{action_html}</div>' if action_html else "") + '</div>')


def alert(title_html, desc_html="", variant=None, icon_name="info", attrs="", cls=""):
    v = f' data-variant="{variant}"' if variant else ""
    c = f' class="{cls}"' if cls else ""
    return (f'<div{c} data-slot="alert" role="note"{v}{_attrs(attrs)}>{icon(icon_name) if icon_name else ""}'
            + (f'<p data-slot="alert-title">{title_html}</p>' if title_html else "")
            + (f'<div data-slot="alert-description">{desc_html}</div>' if desc_html else "") + '</div>')


def tabs(tid, items, label, selected=0, stable=False):
    """shadcn Tabs (Radix anatomy): tablist + triggers (role=tab, aria-controls) + panels (role=tabpanel). items = [(key, label, html)].
    Without JavaScript every panel is visible (the .js class hides the inactive ones), so no content is ever unreachable."""
    trig = "".join(
        f'<button data-slot="tabs-trigger" type="button" role="tab" id="{tid}-t-{k}" aria-controls="{tid}-p-{k}" '
        f'aria-selected="{"true" if i == selected else "false"}" tabindex="{0 if i == selected else -1}">{E(lbl)}</button>'
        for i, (k, lbl, _) in enumerate(items))
    panels = "".join(
        f'<div data-slot="tabs-content" role="tabpanel" id="{tid}-p-{k}" aria-labelledby="{tid}-t-{k}" tabindex="0"'
        f'{"" if i == selected else " data-inactive"}>{body}</div>'
        for i, (k, _, body) in enumerate(items))
    # stable=True (v4.7.1): with JavaScript every panel shares one grid cell, so switching tabs never moves the content below
    return (f'<div data-slot="tabs" class="tabs" data-tabs{" data-tabs-stable" if stable else ""}><div data-slot="tabs-list" role="tablist" aria-label="{E(label)}">{trig}</div>'
            f'{panels}</div>')


def accordion_item(summary_html, body_html, attrs="", open_=False):
    return (f'<details data-slot="accordion-item" class="acc"{_attrs(attrs)}{" open" if open_ else ""}>'
            f'<summary data-slot="accordion-trigger">{summary_html}</summary>'
            f'<div data-slot="accordion-content">{body_html}</div></details>')
