#!/usr/bin/env python3
"""
KDP Christian Book Generator
Génère un dévotionnel chrétien de 30 jours : contenu (Claude) + couverture (Ideogram) + PDF 5x8" + EPUB
Usage: python3 generate_book.py "30 jours pour surmonter l'anxiété avec Jésus"
"""

import os
import sys
import json
import re
import time
import requests
from pathlib import Path
from datetime import datetime

import anthropic

from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    HRFlowable, KeepTogether, Table, TableStyle
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ebooklib import epub

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
AUTHOR    = "John. B"
PAGE_W    = 5 * inch
PAGE_H    = 8 * inch
MARGIN    = 0.75 * inch
CONTENT_W = PAGE_W - 2 * MARGIN
ACCENT    = colors.HexColor("#1a472a")   # vert foncé
GOLD      = colors.HexColor("#c9a84c")   # or


# ─────────────────────────────────────────────
# 1. GÉNÉRATION DU CONTENU (Claude)
# ─────────────────────────────────────────────
def _call_claude(client, system: str, prompt: str) -> str:
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return raw


def _generate_days_batch(client, system: str, title: str, start: int, end: int) -> list:
    prompt = f"""Livre : "{title}"
Génère les jours {start} à {end} d'un dévotionnel chrétien.

Retourne UNIQUEMENT un tableau JSON valide (sans markdown) :
[
  {{
    "number": {start},
    "title": "TITRE EN MAJUSCULES (5-8 mots, accrocheur)",
    "body": "Paragraphe 1 (situation concrète).\\n\\nParagraphe 2 (approfondissement du problème).\\n\\nParagraphe 3 (perspective de Jésus, vérité biblique).\\n\\nParagraphe 4 (invitation directe au lecteur).",
    "verse": "\\"Texte du verset.\\" — Livre chapitre:verset (LS)",
    "challenge": "Aujourd'hui, [défi pratique en 1-2 phrases]."
  }},
  ...
]

IMPORTANT : génère exactement les jours {start} à {end} (soit {end - start + 1} jours).
Chaque champ "body" doit contenir exactement 4 paragraphes séparés par \\n\\n.
N'utilise jamais de guillemets droits dans les textes — utilise des guillemets courbes ou évite-les."""

    raw = _call_claude(client, system, prompt)
    return json.loads(raw)


def generate_content(theme: str) -> dict:
    print(f"📖 Génération du contenu pour : {theme}")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    system = """Tu es un auteur chrétien francophone spécialisé dans les dévotionnels de 30 jours pour KDP.
Tu écris avec un style chaleureux, profond et accessible, en tutoyant directement le lecteur.
Tu connais parfaitement la Bible (version Louis Segond) et cites des versets précis.
IMPORTANT : dans tes réponses JSON, n'utilise jamais de guillemets droits (") dans les valeurs texte — utilise des apostrophes ou reformule."""

    # ── Métadonnées + introduction ──
    print("   → 1/7 : titre + introduction...")
    prompt_intro = f"""Thème : "{theme}"

Retourne UNIQUEMENT du JSON valide (sans markdown) :
{{
  "title": "30 jours pour [...]",
  "subtitle": "Sous-titre accrocheur en 1 phrase.",
  "introduction": "Paragraphe 1.\\n\\nParagraphe 2.\\n\\nParagraphe 3.\\n\\nParagraphe 4.\\n\\nParagraphe 5."
}}"""

    data = json.loads(_call_claude(client, system, prompt_intro))
    title = data["title"]
    data["days"] = []

    # ── 6 lots de 5 jours ──
    batches = [(1,5), (6,10), (11,15), (16,20), (21,25), (26,30)]
    for i, (start, end) in enumerate(batches, 2):
        print(f"   → {i}/7 : jours {start}-{end}...")
        days = _generate_days_batch(client, system, title, start, end)
        data["days"].extend(days)

    # ── Conclusion + prière ──
    print("   → 7/7 : conclusion + prière finale...")
    prompt_end = f"""Livre : "{title}"

Retourne UNIQUEMENT du JSON valide (sans markdown) :
{{
  "a_relire": "Paragraphe 1.\\n\\nParagraphe 2.\\n\\nParagraphe 3.",
  "priere_finale": "Seigneur,\\nLigne 2.\\nLigne 3.\\nLigne 4.\\nLigne 5.\\nLigne 6.\\nLigne 7.\\nLigne 8.\\nLigne 9.\\nLigne 10.\\nLigne 11.\\nLigne 12.\\nLigne 13.\\nLigne 14.\\nLigne 15.\\nAmen."
}}

La prière doit être émouvante, 15 lignes minimum, chaque ligne séparée par \\n."""

    data3 = json.loads(_call_claude(client, system, prompt_end))
    data["a_relire"] = data3["a_relire"]
    data["priere_finale"] = data3["priere_finale"]

    print(f"✅ Contenu généré : {len(data['days'])} jours")
    return data


# ─────────────────────────────────────────────
# 2. GÉNÉRATION DE LA COUVERTURE (Ideogram)
# ─────────────────────────────────────────────
def _add_cover_text(cover_path: Path, title: str, author: str) -> None:
    """Overlay title and author name on the cover image using Pillow."""
    from PIL import Image, ImageDraw, ImageFont
    import textwrap

    img = Image.open(cover_path).convert("RGBA")
    W, H = img.size

    # ── Fonts ──
    font_dir = Path("/usr/share/fonts/truetype")
    try:
        font_title  = ImageFont.truetype(str(font_dir / "dejavu/DejaVuSerif-Bold.ttf"), int(H * 0.055))
        font_sub    = ImageFont.truetype(str(font_dir / "dejavu/DejaVuSerif-BoldItalic.ttf") if (font_dir / "dejavu/DejaVuSerif-BoldItalic.ttf").exists() else str(font_dir / "dejavu/DejaVuSerif-Bold.ttf"), int(H * 0.030))
        font_author = ImageFont.truetype(str(font_dir / "liberation/LiberationSerif-Italic.ttf"), int(H * 0.026))
    except Exception:
        font_title  = ImageFont.load_default()
        font_sub    = font_title
        font_author = font_title

    # ── Gradient overlay top (for title) ──
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    for y in range(int(H * 0.55)):
        alpha = int(180 * (1 - y / (H * 0.55)))
        draw_ov.line([(0, y), (W, y)], fill=(10, 40, 20, alpha))
    # Gradient overlay bottom (for author)
    for y in range(int(H * 0.18)):
        y2 = H - 1 - y
        alpha = int(160 * (1 - y / (H * 0.18)))
        draw_ov.line([(0, y2), (W, y2)], fill=(10, 30, 15, alpha))

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    GOLD_C  = (201, 168, 76, 255)
    WHITE_C = (255, 255, 255, 255)

    # ── Wrap and draw title ──
    max_chars = max(12, int(W / (font_title.size * 0.58)))
    lines = textwrap.wrap(title.upper(), width=max_chars)
    total_h = len(lines) * int(H * 0.065)
    y_start = int(H * 0.12)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        # Shadow
        draw.text((x + 2, y_start + 2), line, font=font_title, fill=(0, 0, 0, 160))
        draw.text((x, y_start), line, font=font_title, fill=WHITE_C)
        y_start += int(H * 0.065)

    # ── Gold separator ──
    sep_y = y_start + int(H * 0.015)
    sep_w = int(W * 0.45)
    sep_x = (W - sep_w) // 2
    draw.rectangle([sep_x, sep_y, sep_x + sep_w, sep_y + 3], fill=GOLD_C)

    # ── Author name at bottom ──
    author_text = f"— {author} —"
    bbox = draw.textbbox((0, 0), author_text, font=font_author)
    aw = bbox[2] - bbox[0]
    ax = (W - aw) // 2
    ay = int(H * 0.90)
    draw.text((ax + 1, ay + 1), author_text, font=font_author, fill=(0, 0, 0, 140))
    draw.text((ax, ay), author_text, font=font_author, fill=GOLD_C)

    img = img.convert("RGB")
    img.save(cover_path, "JPEG", quality=95)


def generate_cover(title: str, subtitle: str, output_dir: Path) -> Path:
    print("🎨 Génération de la couverture avec Ideogram...")

    prompt = (
        "Professional Christian devotional book cover for KDP publishing. "
        "Deep forest green background with warm golden light rays descending from above. "
        "Subtle open Bible and cross motif in lower half, peaceful spiritual atmosphere. "
        "NO text, no letters, no words anywhere on the image. "
        "Clean space at the top third for title overlay. "
        "Professional Christian publishing quality, portrait format, elegant minimalist style."
    )

    payload = {
        "image_request": {
            "prompt": prompt,
            "model": "V_2A",
            "aspect_ratio": "ASPECT_2_3",
            "style_type": "DESIGN",
            "magic_prompt_option": "OFF",
            "num_images": 1
        }
    }

    response = requests.post(
        "https://api.ideogram.ai/generate",
        headers={
            "Api-Key": os.environ["IDEOGRAM_API_KEY"],
            "Content-Type": "application/json"
        },
        json=payload
    )

    if not response.ok:
        print(f"❌ Ideogram error {response.status_code}: {response.text[:300]}")
        response.raise_for_status()

    image_url = response.json()["data"][0]["url"]

    cover_path = output_dir / "cover.jpg"
    img_data = requests.get(image_url).content
    with open(cover_path, "wb") as f:
        f.write(img_data)

    # Overlay title and author name
    _add_cover_text(cover_path, title, AUTHOR)

    print(f"✅ Couverture sauvegardée : {cover_path}")
    return cover_path


# ─────────────────────────────────────────────
# 3. GÉNÉRATION DU PDF (ReportLab, 5x8")
# ─────────────────────────────────────────────
def build_pdf(data: dict, cover_path: Path, output_dir: Path) -> Path:
    print("📄 Création du PDF 5x8\"...")

    safe_title = re.sub(r'[^\w\s-]', '', data['title']).strip().replace(' ', '_')[:60]
    pdf_path = output_dir / f"{safe_title}_KDP_5x8.pdf"

    # ── Styles ──
    def style(name, **kwargs):
        base = {
            "fontName": "Helvetica",
            "fontSize": 11,
            "leading": 16,
            "textColor": colors.HexColor("#1a1a1a"),
        }
        base.update(kwargs)
        return ParagraphStyle(name, **base)

    s_title_page  = style("TitlePage",  fontName="Helvetica-Bold", fontSize=22, leading=28, alignment=TA_CENTER, textColor=ACCENT, spaceAfter=12)
    s_subtitle    = style("Subtitle",   fontName="Helvetica-Oblique", fontSize=13, leading=18, alignment=TA_CENTER, textColor=GOLD, spaceAfter=6)
    s_author      = style("Author",     fontName="Helvetica", fontSize=12, leading=16, alignment=TA_CENTER, textColor=colors.HexColor("#555555"))
    s_chapter     = style("Chapter",    fontName="Helvetica-Bold", fontSize=15, leading=20, alignment=TA_CENTER, textColor=ACCENT, spaceBefore=24, spaceAfter=16)
    s_body        = style("Body",       fontName="Helvetica", fontSize=10.5, leading=16, alignment=TA_JUSTIFY, spaceAfter=8)
    s_verse_label = style("VerseLabel", fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=ACCENT, spaceBefore=12, spaceAfter=4)
    s_verse       = style("Verse",      fontName="Helvetica-Oblique", fontSize=10, leading=15, alignment=TA_LEFT, leftIndent=12, textColor=colors.HexColor("#333333"), spaceAfter=12)
    s_chal_label  = style("ChalLabel",  fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=GOLD, spaceBefore=8, spaceAfter=4)
    s_challenge   = style("Challenge",  fontName="Helvetica", fontSize=10, leading=15, leftIndent=12, spaceAfter=8)
    s_toc_title   = style("TocTitle",   fontName="Helvetica-Bold", fontSize=14, leading=20, alignment=TA_CENTER, textColor=ACCENT, spaceAfter=16, spaceBefore=8)
    s_toc_entry   = style("TocEntry",   fontName="Helvetica", fontSize=9.5, leading=14, textColor=colors.HexColor("#333333"))
    s_section     = style("Section",    fontName="Helvetica-Bold", fontSize=13, leading=18, alignment=TA_CENTER, textColor=ACCENT, spaceBefore=20, spaceAfter=12)
    s_intro       = style("Intro",      fontName="Helvetica", fontSize=10.5, leading=16, alignment=TA_JUSTIFY, spaceAfter=8)

    # Styles supplémentaires
    s_toc_entry_pg = style("TocEntryPg", fontName="Helvetica", fontSize=9.5, leading=15,
                           textColor=colors.HexColor("#333333"))
    s_sommaire_day = style("SommaireDay", fontName="Helvetica-Bold", fontSize=10, leading=14,
                           textColor=ACCENT, spaceBefore=8, spaceAfter=2)
    s_sommaire_txt = style("SommaireTxt", fontName="Helvetica-Oblique", fontSize=9.5, leading=14,
                           textColor=colors.HexColor("#444444"), leftIndent=8, spaceAfter=6)

    # Page numbers: title=1, toc=2-3, intro=4-5, sommaire=6-11, days start at 12
    DAYS_START = 12

    def toc_line(label, page_num):
        """Return a dotted leader TOC line using a two-column Table."""
        dot_leader = " . " * 30
        data_row = [[Paragraph(label, s_toc_entry_pg),
                     Paragraph(str(page_num), style("PgNum", fontName="Helvetica",
                               fontSize=9.5, leading=15, alignment=TA_RIGHT,
                               textColor=colors.HexColor("#333333")))]]
        t = Table(data_row, colWidths=[CONTENT_W * 0.88, CONTENT_W * 0.12])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))
        return t

    def first_sentence(text: str) -> str:
        """Extract first 1-2 sentences as teaser."""
        import re as _re
        sents = _re.split(r'(?<=[.!?])\s+', text.strip())
        result = sents[0] if sents else text[:120]
        if len(sents) > 1 and len(result) < 80:
            result += " " + sents[1]
        return result[:200]

    story = []

    # ── 1. Page de titre ──
    story.append(Spacer(1, 1.2 * inch))
    story.append(Paragraph(data['title'].upper(), s_title_page))
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph(data['subtitle'], s_subtitle))
    story.append(Spacer(1, 0.4 * inch))
    story.append(HRFlowable(width="55%", thickness=1.5, color=GOLD, hAlign="CENTER"))
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(AUTHOR, s_author))
    story.append(PageBreak())

    # ── 2. Table des matières (Contents) ──
    story.append(Paragraph("Contents", s_toc_title))
    story.append(Spacer(1, 0.2 * inch))
    for day in data['days']:
        label = f"JOUR {day['number']} – {day['title'].upper()}"
        pg = DAYS_START + (day['number'] - 1) * 2
        story.append(toc_line(label, pg))
    # Footer sections
    a_relire_pg = DAYS_START + 30 * 2
    priere_pg   = a_relire_pg + 1
    story.append(toc_line("À RELIRE EN TEMPS VOULU…", a_relire_pg))
    story.append(toc_line("PRIÈRE FINALE", priere_pg))
    story.append(PageBreak())

    # ── 3. Introduction ──
    story.append(Paragraph("Introduction", s_section))
    story.append(Spacer(1, 0.2 * inch))
    for para in data['introduction'].split('\n\n'):
        para = para.strip()
        if para:
            story.append(Paragraph(para, s_intro))
    story.append(PageBreak())

    # ── 4. Sommaire détaillé (teasers) ──
    story.append(Paragraph("SOMMAIRE", s_toc_title))
    story.append(Spacer(1, 0.1 * inch))
    for day in data['days']:
        day_label = f"Jour {day['number']} – {day['title'].title()}"
        teaser = first_sentence(day['body'])
        story.append(Paragraph(day_label, s_sommaire_day))
        story.append(Paragraph(teaser, s_sommaire_txt))
    story.append(PageBreak())

    # ── 5. 30 Jours ──
    for day in data['days']:
        story.append(Paragraph(f"JOUR {day['number']} – {day['title'].upper()}", s_chapter))
        story.append(HRFlowable(width="40%", thickness=0.5, color=GOLD, hAlign="CENTER", spaceAfter=14))

        for para in day['body'].split('\n\n'):
            para = para.strip()
            if para:
                story.append(Paragraph(para, s_body))

        story.append(Paragraph("✦ Verset du jour", s_verse_label))
        story.append(Paragraph(day['verse'], s_verse))
        story.append(Paragraph("✦ Pour aller plus loin", s_chal_label))
        story.append(Paragraph(day['challenge'], s_challenge))
        story.append(PageBreak())

    # ── 6. À relire ──
    story.append(Paragraph("À RELIRE EN TEMPS VOULU…", s_section))
    story.append(Spacer(1, 0.2 * inch))
    for para in data['a_relire'].split('\n\n'):
        para = para.strip()
        if para:
            story.append(Paragraph(para, s_intro))
    story.append(PageBreak())

    # ── 7. Prière finale ──
    story.append(Paragraph("PRIÈRE FINALE", s_section))
    story.append(Spacer(1, 0.2 * inch))
    for line in data['priere_finale'].split('\n'):
        line = line.strip()
        if line:
            story.append(Paragraph(line, s_intro))
        else:
            story.append(Spacer(1, 4))

    # ── Build ──
    def add_page_number(canvas_obj, doc):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(colors.HexColor("#999999"))
        page_num = canvas_obj.getPageNumber()
        if page_num > 2:
            canvas_obj.drawCentredString(PAGE_W / 2, 0.4 * inch, str(page_num))
        canvas_obj.restoreState()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=(PAGE_W, PAGE_H),
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN + 0.1 * inch,
        title=data['title'],
        author=AUTHOR,
    )
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"✅ PDF créé : {pdf_path}")
    return pdf_path


# ─────────────────────────────────────────────
# 4. GÉNÉRATION DE L'EPUB
# ─────────────────────────────────────────────
def build_epub(data: dict, cover_path: Path, output_dir: Path) -> Path:
    print("📱 Création de l'EPUB...")

    safe_title = re.sub(r'[^\w\s-]', '', data['title']).strip().replace(' ', '_')[:60]
    epub_path = output_dir / f"{safe_title}_KDP.epub"

    book = epub.EpubBook()
    book.set_title(data['title'])
    book.set_language("fr")
    book.add_author(AUTHOR)
    book.set_identifier(f"kdp-{int(time.time())}")

    css = epub.EpubItem(
        uid="style", file_name="style.css", media_type="text/css",
        content="""
body { font-family: Georgia, serif; margin: 1em 1.5em; color: #1a1a1a; }
h1 { color: #1a472a; font-size: 1.6em; text-align: center; margin: 1.5em 0 0.5em; }
h2 { color: #1a472a; font-size: 1.2em; text-align: center; margin: 2em 0 0.8em; border-bottom: 1px solid #c9a84c; padding-bottom: 0.3em; }
h3 { color: #c9a84c; font-size: 1em; margin: 1.2em 0 0.3em; }
p { text-align: justify; line-height: 1.7; margin: 0.5em 0; }
blockquote { font-style: italic; border-left: 3px solid #c9a84c; padding-left: 1em; margin: 1em 0; color: #444; }
.challenge { background: #f9f6ef; border-left: 3px solid #1a472a; padding: 0.7em 1em; margin: 1em 0; }
hr { border: none; border-top: 1px solid #c9a84c; margin: 1.5em auto; width: 50%; }
"""
    )
    book.add_item(css)

    # Couverture
    with open(cover_path, "rb") as f:
        cover_data = f.read()
    book.set_cover("cover.jpg", cover_data)

    spine = ["nav"]
    toc = []

    def make_chapter(uid, title, body_html):
        ch = epub.EpubHtml(title=title, file_name=f"{uid}.xhtml", lang="fr")
        ch.add_item(css)
        ch.content = f"<html><body>{body_html}</body></html>"
        book.add_item(ch)
        spine.append(ch)
        toc.append(epub.Link(f"{uid}.xhtml", title, uid))
        return ch

    # Introduction
    intro_html = f"<h1>{data['title']}</h1><h2>Introduction</h2>"
    intro_html += "".join(f"<p>{p.strip()}</p>" for p in data['introduction'].split('\n\n') if p.strip())
    make_chapter("intro", "Introduction", intro_html)

    # Jours
    for day in data['days']:
        body_html = f"<h2>JOUR {day['number']} – {day['title']}</h2>"
        body_html += "".join(f"<p>{p.strip()}</p>" for p in day['body'].split('\n\n') if p.strip())
        body_html += f"<h3>✦ Verset du jour</h3><blockquote>{day['verse']}</blockquote>"
        body_html += f"<h3>✦ Pour aller plus loin</h3><div class='challenge'><p>{day['challenge']}</p></div>"
        make_chapter(f"jour{day['number']:02d}", f"Jour {day['number']} – {day['title'].title()}", body_html)

    # À relire
    relire_html = "<h2>À RELIRE EN TEMPS VOULU…</h2>"
    relire_html += "".join(f"<p>{p.strip()}</p>" for p in data['a_relire'].split('\n\n') if p.strip())
    make_chapter("relire", "À relire en temps voulu", relire_html)

    # Prière finale
    priere_html = "<h2>PRIÈRE FINALE</h2>"
    for line in data['priere_finale'].split('\n'):
        line = line.strip()
        priere_html += f"<p>{line}</p>" if line else "<br/>"
    make_chapter("priere", "Prière finale", priere_html)

    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    epub.write_epub(str(epub_path), book)
    print(f"✅ EPUB créé : {epub_path}")
    return epub_path


# ─────────────────────────────────────────────
# 5. PIPELINE PRINCIPAL
# ─────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_book.py \"thème du livre\"")
        print("Exemple: python3 generate_book.py \"30 jours pour surmonter l'anxiété avec Jésus\"")
        sys.exit(1)

    theme = sys.argv[1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    # Vérification des clés API
    for key in ["ANTHROPIC_API_KEY", "IDEOGRAM_API_KEY"]:
        if not os.environ.get(key):
            print(f"❌ Variable manquante : {key}")
            sys.exit(1)

    # Dossier de sortie (stable, sans timestamp pour permettre la reprise)
    safe = re.sub(r'[^\w\s-]', '', theme).strip().replace(' ', '_')[:50]
    output_dir = Path(f"/root/kdp-automation/output/{safe}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🚀 Génération du livre : {theme}")
    print(f"📁 Dossier : {output_dir}\n")

    # Reprise depuis JSON existant si disponible
    json_path = output_dir / "content.json"
    if json_path.exists():
        print("📂 Contenu existant trouvé, reprise depuis le JSON...")
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = generate_content(theme)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    cover_path = generate_cover(data['title'], data['subtitle'], output_dir)
    pdf_path   = build_pdf(data, cover_path, output_dir)
    epub_path  = build_epub(data, cover_path, output_dir)

    print(f"\n✅ Livre généré avec succès !")
    print(f"   📄 PDF   : {pdf_path}")
    print(f"   📱 EPUB  : {epub_path}")
    print(f"   🖼️  Cover : {cover_path}")
    print(f"   📁 Dossier : {output_dir}")


if __name__ == "__main__":
    main()
