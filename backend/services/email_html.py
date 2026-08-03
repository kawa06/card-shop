"""Responsive HTML email layout with brand wrapper, card design, and dark-mode support."""

from __future__ import annotations

import html
import json
from typing import Any

import models_email
from config import settings


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _sns_links_html(brand: models_email.EmailBrandSettings) -> str:
    try:
        sns = json.loads(brand.sns_links_json or "[]")
    except json.JSONDecodeError:
        sns = []
    parts: list[str] = []
    for link in sns:
        if isinstance(link, dict) and link.get("url"):
            label = _esc(link.get("label") or link["url"])
            parts.append(
                f'<a href="{_esc(link["url"])}" style="color:#6366f1;text-decoration:none;margin:0 8px;">{label}</a>'
            )
    return "".join(parts)


def _footer_links_html(brand: models_email.EmailBrandSettings, variables: dict[str, Any]) -> str:
    links: list[str] = []
    terms = brand.terms_url or variables.get("termsUrl", "")
    contact = brand.contact_url or variables.get("contactUrl", "")
    privacy = brand.privacy_url or variables.get("privacyUrl", "")
    if terms:
        links.append(f'<a href="{_esc(terms)}" style="color:#6366f1;text-decoration:none;">利用規約</a>')
    if contact:
        links.append(f'<a href="{_esc(contact)}" style="color:#6366f1;text-decoration:none;">お問い合わせ</a>')
    if privacy:
        links.append(f'<a href="{_esc(privacy)}" style="color:#6366f1;text-decoration:none;">プライバシー</a>')
    sns = _sns_links_html(brand)
    if sns:
        links.append(sns)
    if not links:
        return ""
    return (
        '<p style="margin:12px 0 0;font-size:12px;line-height:1.6;color:#64748b;">'
        + " &nbsp;|&nbsp; ".join(links)
        + "</p>"
    )


def _company_block(brand: models_email.EmailBrandSettings) -> str:
    parts: list[str] = []
    if brand.company_name:
        parts.append(f"<strong>{_esc(brand.company_name)}</strong>")
    if brand.company_address:
        parts.append(_esc(brand.company_address))
    contact_bits: list[str] = []
    if brand.contact_email:
        contact_bits.append(f'<a href="mailto:{_esc(brand.contact_email)}" style="color:#6366f1;">{_esc(brand.contact_email)}</a>')
    if brand.contact_phone:
        contact_bits.append(_esc(brand.contact_phone))
    if contact_bits:
        parts.append(" / ".join(contact_bits))
    if not parts:
        return ""
    return (
        '<p style="margin:8px 0 0;font-size:11px;line-height:1.6;color:#94a3b8;">'
        + "<br>".join(parts)
        + "</p>"
    )


def wrap_with_brand(body_html: str, brand: models_email.EmailBrandSettings, variables: dict[str, Any]) -> str:
    """Wrap template body in a mobile-friendly card layout with dark-mode meta hints."""
    shop = _esc(variables.get("shopName") or settings.SITE_NAME or "KRX TCG")
    logo = brand.logo_url or variables.get("logoUrl", "")
    brand_color = (brand.brand_color or "#fbbf24").strip() or "#fbbf24"
    footer = _esc(brand.footer_text or f"© {settings.SITE_NAME or 'KRX TCG'}")
    sender = _esc(brand.sender_name or settings.MAIL_FROM_NAME or shop)

    if logo:
        header_html = (
            f'<img src="{_esc(logo)}" alt="{shop}" width="160" '
            'style="display:block;max-width:160px;height:auto;margin:0 auto 8px;" />'
        )
    else:
        header_html = (
            f'<p style="margin:0;font-size:20px;font-weight:700;color:{_esc(brand_color)};'
            f'letter-spacing:0.02em;text-align:center;">{shop}</p>'
        )

    footer_links = _footer_links_html(brand, variables)
    company = _company_block(brand)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="color-scheme" content="light dark" />
  <meta name="supported-color-schemes" content="light dark" />
  <title>{shop}</title>
  <style>
    @media (prefers-color-scheme: dark) {{
      .email-bg {{ background-color: #0f172a !important; }}
      .email-card {{ background-color: #1e293b !important; border-color: #334155 !important; }}
      .email-text {{ color: #e2e8f0 !important; }}
      .email-muted {{ color: #94a3b8 !important; }}
      .email-hr {{ border-color: #334155 !important; }}
    }}
    @media only screen and (max-width: 620px) {{
      .email-card {{ padding: 20px 16px !important; }}
      .email-body {{ font-size: 15px !important; }}
    }}
  </style>
</head>
<body class="email-bg" style="margin:0;padding:0;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Hiragino Sans','Noto Sans JP',sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">
          <tr>
            <td style="padding:0 0 16px;text-align:center;">
              {header_html}
              <p class="email-muted" style="margin:4px 0 0;font-size:12px;color:#64748b;">{sender}</p>
            </td>
          </tr>
          <tr>
            <td class="email-card" style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:28px 24px;box-shadow:0 1px 3px rgba(0,0,0,0.06);">
              <div class="email-body email-text" style="font-size:16px;line-height:1.7;color:#1e293b;">
                {body_html}
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 8px 0;text-align:center;">
              <hr class="email-hr" style="border:0;border-top:1px solid #e2e8f0;margin:0 0 12px;" />
              <p class="email-muted" style="margin:0;font-size:12px;line-height:1.6;color:#64748b;">{footer}</p>
              {footer_links}
              {company}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def button_html(text: str, url: str, *, color: str = "#fbbf24") -> str:
    """Primary CTA button block for templates."""
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:20px auto;">'
        f'<tr><td align="center" style="border-radius:8px;background:{_esc(color)};">'
        f'<a href="{_esc(url)}" target="_blank" rel="noopener" '
        f'style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:600;'
        f'color:#111827;text-decoration:none;border-radius:8px;">{_esc(text)}</a>'
        f"</td></tr></table>"
    )
