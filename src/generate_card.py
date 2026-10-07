import os
import datetime
from PIL import Image, ImageDraw, ImageFont

def _get_font(size: int, bold: bool = False):
    """
    Attempts to load a clean TrueType font from system paths.
    Falls back to default bitmap font if no TTF is found.
    """
    candidate_fonts = [
        # Windows fonts
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        # Ubuntu fonts
        "/usr/share/fonts/truetype/ubuntu/UbuntuSans[wdth,wght].ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf" if bold else "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
        # DejaVu fonts
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        # Liberation fonts
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # FreeSans
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    
    for path in candidate_fonts:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
                
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()

def _draw_header(draw, W, title_suffix="DAILY MARKET BRIEF"):
    font_title = _get_font(34, bold=True)
    font_subtitle = _get_font(18, bold=False)
    
    # Top Header Background Accent Line
    draw.line([(0, 0), (W, 0)], fill="#38bdf8", width=6)
    
    # Header Left: Title & Subtitle
    draw.text((50, 35), "BRIEFIN", fill="#38bdf8", font=font_title)
    bbox_briefin = draw.textbbox((50, 35), "BRIEFIN", font=font_title)
    draw.text((bbox_briefin[2] + 12, 35), f"• {title_suffix}", fill="#f1f5f9", font=font_title)
    
    today_str = datetime.datetime.now().strftime("%d %B %Y")
    draw.text((50, 80), f"IDX Market Pulse  |  {today_str}", fill="#94a3b8", font=font_subtitle)

def _draw_ihsg_badge(draw, normalized_data, box_coords=(780, 28, 1150, 118)):
    font_badge = _get_font(16, bold=True)
    font_ihsg_val = _get_font(28, bold=True)
    
    ihsg = normalized_data.get("ihsg", {})
    price = ihsg.get("price", "N/A")
    change = ihsg.get("change", 0)
    pct = ihsg.get("percent_change", 0)
    
    is_positive = (change >= 0) if isinstance(change, (int, float)) else True
    direction_sign = "+" if is_positive else ""
    
    price_str = f"{price:,.2f}" if isinstance(price, (int, float)) else str(price)
    change_str = f"{direction_sign}{change:,.2f} ({direction_sign}{pct:.2f}%)" if isinstance(change, (int, float)) else f"{change} ({pct}%)"
    
    box_x0, box_y0, box_x1, box_y1 = box_coords
    draw.rounded_rectangle([box_x0, box_y0, box_x1, box_y1], radius=12, fill="#1e293b", outline="#334155", width=1)
    
    draw.text((box_x0 + 20, box_y0 + 12), "IHSG COMPOSITE", fill="#94a3b8", font=font_badge)
    # Angka harga IHSG (Putih bersih)
    draw.text((box_x0 + 20, box_y0 + 40), price_str, fill="#ffffff", font=font_ihsg_val)
    
    c_bbox = draw.textbbox((0, 0), change_str, font=font_badge)
    c_w = c_bbox[2] - c_bbox[0]
    badge_bg = "#15803d" if is_positive else "#b91c1c"
    badge_x1 = box_x1 - 15
    badge_x0 = badge_x1 - c_w - 20
    badge_y0, badge_y1 = box_y0 + 42, box_y0 + 76
    draw.rounded_rectangle([badge_x0, badge_y0, badge_x1, badge_y1], radius=8, fill=badge_bg)
    # PERBAIKAN: Angka di container IHSG komposit kini diwarnai PUTIH BENERAN (#ffffff)
    draw.text((badge_x0 + 10, badge_y0 + 7), change_str, fill="#ffffff", font=font_badge)

def _draw_footer(draw, W, H):
    font_footer = _get_font(17, bold=False)
    footer_y = H - 52
    draw.text((50, footer_y), "Automated by Briefin", fill="#94a3b8", font=font_footer)
    
    credit_str = "Sectors API v2 • AI Summarizer"
    c_bbox = draw.textbbox((0, 0), credit_str, font=font_footer)
    draw.text((W - 50 - (c_bbox[2] - c_bbox[0]), footer_y), credit_str, fill="#38bdf8", font=font_footer)

# ==============================================================================
# GAMBAR 1: IHSG + Top 5 Gainers & Losers (Versi Standar yang Disempurnakan)
# ==============================================================================
def generate_card_v1(normalized_data: dict, output_path: str) -> str:
    W, H = 1200, 750
    img = Image.new("RGB", (W, H), color="#0f172a")  # Slate 900
    draw = ImageDraw.Draw(img)
    
    _draw_header(draw, W, "DAILY MARKET BRIEF")
    _draw_ihsg_badge(draw, normalized_data, (780, 28, 1150, 118))
    
    font_section = _get_font(21, bold=True)
    font_row_bold = _get_font(20, bold=True)
    font_row = _get_font(19, bold=False)
    font_badge = _get_font(16, bold=True)
    
    panel_y0, panel_y1 = 145, 665
    left_x0, left_x1 = 50, 585
    right_x0, right_x1 = 615, 1150
    
    # Left: Top Gainers Panel
    draw.rounded_rectangle([left_x0, panel_y0, left_x1, panel_y1], radius=16, fill="#1e293b", outline="#334155", width=1)
    draw.rounded_rectangle([left_x0, panel_y0, left_x1, panel_y0 + 55], radius=16, fill="#14532d")
    draw.rectangle([left_x0, panel_y0 + 35, left_x1, panel_y0 + 55], fill="#14532d")
    draw.ellipse([left_x0 + 25, panel_y0 + 22, left_x0 + 37, panel_y0 + 34], fill="#4ade80")
    draw.text((left_x0 + 48, panel_y0 + 16), "TOP 5 GAINERS", fill="#4ade80", font=font_section)
    
    # Right: Top Losers Panel
    draw.rounded_rectangle([right_x0, panel_y0, right_x1, panel_y1], radius=16, fill="#1e293b", outline="#334155", width=1)
    draw.rounded_rectangle([right_x0, panel_y0, right_x1, panel_y0 + 55], radius=16, fill="#7f1d1d")
    draw.rectangle([right_x0, panel_y0 + 35, right_x1, panel_y0 + 55], fill="#7f1d1d")
    draw.ellipse([right_x0 + 25, panel_y0 + 22, right_x0 + 37, panel_y0 + 34], fill="#f87171")
    draw.text((right_x0 + 48, panel_y0 + 16), "TOP 5 LOSERS", fill="#f87171", font=font_section)
    
    # Table Header Row
    for px0, px1 in [(left_x0, left_x1), (right_x0, right_x1)]:
        hdr_y = panel_y0 + 68
        draw.text((px0 + 25, hdr_y), "#", fill="#64748b", font=font_badge)
        draw.text((px0 + 75, hdr_y), "TICKER", fill="#64748b", font=font_badge)
        draw.text((px0 + 270, hdr_y), "CLOSE", fill="#64748b", font=font_badge)
        draw.text((px1 - 100, hdr_y), "CHANGE", fill="#64748b", font=font_badge)
        draw.line([(px0 + 20, hdr_y + 24), (px1 - 20, hdr_y + 24)], fill="#334155", width=1)
    
    # Gainers Rows
    gainers = normalized_data.get("gainers", [])[:5]
    row_start_y = panel_y0 + 105
    row_spacing = 80
    for i in range(5):
        cy = row_start_y + (i * row_spacing)
        if i % 2 == 1:
            draw.rounded_rectangle([left_x0 + 10, cy - 8, left_x1 - 10, cy + 58], radius=8, fill="#172554")
        if i < len(gainers):
            g = gainers[i]
            sym = g.get("symbol", "N/A").replace(".JK", "")
            prc = g.get("price", 0)
            pct_val = g.get("percent_change", 0)
            draw.text((left_x0 + 25, cy + 12), f"{i+1}", fill="#94a3b8", font=font_row_bold)
            draw.text((left_x0 + 75, cy + 12), sym, fill="#f8fafc", font=font_row_bold)
            prc_text = f"Rp {prc:,.0f}" if isinstance(prc, (int, float)) else str(prc)
            draw.text((left_x0 + 270, cy + 14), prc_text, fill="#cbd5e1", font=font_row)
            
            badge_rect = [left_x1 - 130, cy + 8, left_x1 - 20, cy + 44]
            draw.rounded_rectangle(badge_rect, radius=8, fill="#166534")
            draw.text((badge_rect[0] + 12, cy + 14), f"+{pct_val:.2f}%", fill="#ffffff", font=font_row_bold)
        else:
            draw.text((left_x0 + 75, cy + 12), "-", fill="#64748b", font=font_row)
            
    # Losers Rows
    losers = normalized_data.get("losers", [])[:5]
    for i in range(5):
        cy = row_start_y + (i * row_spacing)
        if i % 2 == 1:
            draw.rounded_rectangle([right_x0 + 10, cy - 8, right_x1 - 10, cy + 58], radius=8, fill="#271a25")
        if i < len(losers):
            l = losers[i]
            sym = l.get("symbol", "N/A").replace(".JK", "")
            prc = l.get("price", 0)
            pct_val = l.get("percent_change", 0)
            draw.text((right_x0 + 25, cy + 12), f"{i+1}", fill="#94a3b8", font=font_row_bold)
            draw.text((right_x0 + 75, cy + 12), sym, fill="#f8fafc", font=font_row_bold)
            prc_text = f"Rp {prc:,.0f}" if isinstance(prc, (int, float)) else str(prc)
            draw.text((right_x0 + 270, cy + 14), prc_text, fill="#cbd5e1", font=font_row)
            
            badge_rect = [right_x1 - 130, cy + 8, right_x1 - 20, cy + 44]
            draw.rounded_rectangle(badge_rect, radius=8, fill="#991b1b")
            draw.text((badge_rect[0] + 12, cy + 14), f"{pct_val:.2f}%", fill="#ffffff", font=font_row_bold)
        else:
            draw.text((right_x0 + 75, cy + 12), "-", fill="#64748b", font=font_row)
            
    _draw_footer(draw, W, H)
    img.save(output_path, "PNG", quality=95)
    return os.path.abspath(output_path)

# ==============================================================================
# GAMBAR 2: Sektor IDX & Macro/Watchlist Radar
# ==============================================================================
def generate_card_v2(normalized_data: dict, output_path: str) -> str:
    W, H = 1200, 750
    img = Image.new("RGB", (W, H), color="#090d16")  # Deep Midnight Blue
    draw = ImageDraw.Draw(img)
    
    _draw_header(draw, W, "SECTOR & MACRO RADAR")
    _draw_ihsg_badge(draw, normalized_data, (780, 28, 1150, 118))
    
    font_section = _get_font(21, bold=True)
    font_row_bold = _get_font(19, bold=True)
    font_row = _get_font(17, bold=False)
    font_badge = _get_font(15, bold=True)
    
    panel_y0, panel_y1 = 145, 665
    left_x0, left_x1 = 50, 680
    right_x0, right_x1 = 710, 1150
    
    # Left: Sektor IDX Heatmap
    draw.rounded_rectangle([left_x0, panel_y0, left_x1, panel_y1], radius=16, fill="#111827", outline="#1f2937", width=1)
    draw.rounded_rectangle([left_x0, panel_y0, left_x1, panel_y0 + 52], radius=16, fill="#1e3a8a")
    draw.rectangle([left_x0, panel_y0 + 32, left_x1, panel_y0 + 52], fill="#1e3a8a")
    draw.text((left_x0 + 25, panel_y0 + 14), "📊 IDX SECTOR MOVEMENT", fill="#60a5fa", font=font_section)
    
    mock_sectors = [
        ("Financials (IDXFINANCE)", "+0.85%", True, 0.75),
        ("Energy (IDXENERGY)", "+1.42%", True, 0.90),
        ("Basic Materials (IDXBASIC)", "-0.34%", False, 0.40),
        ("Technology (IDXTECHNO)", "+2.15%", True, 0.95),
        ("Consumer Non-Cyclical", "-0.18%", False, 0.30),
        ("Infrastructure (IDXINFRA)", "+0.45%", True, 0.60),
    ]
    
    sy = panel_y0 + 72
    for name, change, is_pos, bar_ratio in mock_sectors:
        draw.text((left_x0 + 25, sy), name, fill="#f3f4f6", font=font_row_bold)
        badge_color = "#16a34a" if is_pos else "#dc2626"
        c_bbox = draw.textbbox((0, 0), change, font=font_badge)
        bw = c_bbox[2] - c_bbox[0]
        draw.rounded_rectangle([left_x1 - 35 - bw, sy - 2, left_x1 - 20, sy + 24], radius=6, fill=badge_color)
        draw.text((left_x1 - 28 - bw, sy + 2), change, fill="#ffffff", font=font_badge)
        
        # Mini bar meter
        bar_bg_w = (left_x1 - left_x0 - 50)
        draw.rounded_rectangle([left_x0 + 25, sy + 30, left_x0 + 25 + bar_bg_w, sy + 36], radius=3, fill="#374151")
        fill_color = "#22c55e" if is_pos else "#ef4444"
        draw.rounded_rectangle([left_x0 + 25, sy + 30, left_x0 + 25 + int(bar_bg_w * bar_ratio), sy + 36], radius=3, fill=fill_color)
        sy += 72
        
    # Right: Macro & Foreign Flow Box
    draw.rounded_rectangle([right_x0, panel_y0, right_x1, panel_y0 + 240], radius=16, fill="#111827", outline="#1f2937", width=1)
    draw.rounded_rectangle([right_x0, panel_y0, right_x1, panel_y0 + 48], radius=16, fill="#312e81")
    draw.rectangle([right_x0, panel_y0 + 30, right_x1, panel_y0 + 48], fill="#312e81")
    draw.text((right_x0 + 20, panel_y0 + 12), "🌍 GLOBAL MACRO & COMMODITIES", fill="#a5b4fc", font=font_section)
    
    macros = [
        ("Brent Crude Oil", "$82.40 / bbl", "+0.65%", True),
        ("Gold (XAU/USD)", "$2,645 / oz", "+1.12%", True),
        ("USD / IDR", "Rp 15,640", "-0.15%", True),
        ("Net Foreign Flow", "+Rp 428.5 B (Net Buy)", "BULLISH", True)
    ]
    my = panel_y0 + 64
    for label, val, chg, pos in macros:
        draw.text((right_x0 + 20, my), label, fill="#9ca3af", font=font_row)
        draw.text((right_x0 + 20, my + 20), val, fill="#f9fafb", font=font_row_bold)
        chg_color = "#4ade80" if pos else "#f87171"
        draw.text((right_x1 - 95, my + 20), chg, fill=chg_color, font=font_badge)
        my += 44

    # Right Bottom: Technical Watchlist
    draw.rounded_rectangle([right_x0, panel_y0 + 260, right_x1, panel_y1], radius=16, fill="#111827", outline="#1f2937", width=1)
    draw.rounded_rectangle([right_x0, panel_y0 + 260, right_x1, panel_y0 + 308], radius=16, fill="#065f46")
    draw.rectangle([right_x0, panel_y0 + 290, right_x1, panel_y0 + 308], fill="#065f46")
    draw.text((right_x0 + 20, panel_y0 + 272), "🎯 TECHNICAL WATCHLIST", fill="#6ee7b7", font=font_section)
    
    watch_items = [
        ("BBRI", "Breakout resistance 5,100, akumulasi asing"),
        ("MEDC", "Menguat mengikuti katalis harga minyak"),
        ("ASII", "Rebound teknikal kuat di area support 4,800")
    ]
    wy = panel_y0 + 322
    for ticker, note in watch_items:
        draw.text((right_x0 + 20, wy), ticker, fill="#facc15", font=font_row_bold)
        draw.text((right_x0 + 20, wy + 24), note, fill="#94a3b8", font=font_row)
        wy += 58
        
    _draw_footer(draw, W, H)
    img.save(output_path, "PNG", quality=95)
    return os.path.abspath(output_path)

# ==============================================================================
# GAMBAR 3: Executive All-in-One Dashboard (Komprehensif & Lengkap)
# ==============================================================================
def generate_card_v3(normalized_data: dict, output_path: str) -> str:
    W, H = 1200, 850
    img = Image.new("RGB", (W, H), color="#080c14")
    draw = ImageDraw.Draw(img)
    
    _draw_header(draw, W, "ALL-IN-ONE EXECUTIVE BRIEF")
    _draw_ihsg_badge(draw, normalized_data, (780, 28, 1150, 118))
    
    font_section = _get_font(19, bold=True)
    font_bold = _get_font(17, bold=True)
    font_regular = _get_font(16, bold=False)
    font_badge = _get_font(14, bold=True)
    
    # 3-Column Layout:
    # Col 1 (Gainers), Col 2 (Losers), Col 3 (Sektor & Macro Watchlist)
    top_y = 145
    col_h = 635
    col_w = 340
    gap = 25
    c1_x0 = 50
    c2_x0 = c1_x0 + col_w + gap
    c3_x0 = c2_x0 + col_w + gap
    
    # Column 1: Gainers
    draw.rounded_rectangle([c1_x0, top_y, c1_x0 + col_w, top_y + col_h], radius=14, fill="#111827", outline="#1f2937", width=1)
    draw.rounded_rectangle([c1_x0, top_y, c1_x0 + col_w, top_y + 46], radius=14, fill="#14532d")
    draw.rectangle([c1_x0, top_y + 26, c1_x0 + col_w, top_y + 46], fill="#14532d")
    draw.text((c1_x0 + 15, top_y + 12), "🚀 TOP 5 GAINERS", fill="#4ade80", font=font_section)
    
    gainers = normalized_data.get("gainers", [])[:5]
    gy = top_y + 65
    for i, g in enumerate(gainers):
        sym = g.get("symbol", "N/A").replace(".JK", "")
        prc = g.get("price", 0)
        pct = g.get("percent_change", 0)
        draw.text((c1_x0 + 15, gy), f"{i+1}. {sym}", fill="#f8fafc", font=font_bold)
        draw.text((c1_x0 + 15, gy + 22), f"Rp {prc:,.0f}" if isinstance(prc, (int, float)) else str(prc), fill="#94a3b8", font=font_regular)
        draw.rounded_rectangle([c1_x0 + col_w - 95, gy + 4, c1_x0 + col_w - 15, gy + 32], radius=6, fill="#166534")
        draw.text((c1_x0 + col_w - 85, gy + 8), f"+{pct:.2f}%", fill="#ffffff", font=font_badge)
        gy += 70
        
    # Column 2: Losers
    draw.rounded_rectangle([c2_x0, top_y, c2_x0 + col_w, top_y + col_h], radius=14, fill="#111827", outline="#1f2937", width=1)
    draw.rounded_rectangle([c2_x0, top_y, c2_x0 + col_w, top_y + 46], radius=14, fill="#7f1d1d")
    draw.rectangle([c2_x0, top_y + 26, c2_x0 + col_w, top_y + 46], fill="#7f1d1d")
    draw.text((c2_x0 + 15, top_y + 12), "🔻 TOP 5 LOSERS", fill="#f87171", font=font_section)
    
    losers = normalized_data.get("losers", [])[:5]
    ly = top_y + 65
    for i, l in enumerate(losers):
        sym = l.get("symbol", "N/A").replace(".JK", "")
        prc = l.get("price", 0)
        pct = l.get("percent_change", 0)
        draw.text((c2_x0 + 15, ly), f"{i+1}. {sym}", fill="#f8fafc", font=font_bold)
        draw.text((c2_x0 + 15, ly + 22), f"Rp {prc:,.0f}" if isinstance(prc, (int, float)) else str(prc), fill="#94a3b8", font=font_regular)
        draw.rounded_rectangle([c2_x0 + col_w - 95, ly + 4, c2_x0 + col_w - 15, ly + 32], radius=6, fill="#991b1b")
        draw.text((c2_x0 + col_w - 85, ly + 8), f"{pct:.2f}%", fill="#ffffff", font=font_badge)
        ly += 70

    # Column 3: Sektor & Radar
    draw.rounded_rectangle([c3_x0, top_y, c3_x0 + col_w + 35, top_y + col_h], radius=14, fill="#111827", outline="#1f2937", width=1)
    draw.rounded_rectangle([c3_x0, top_y, c3_x0 + col_w + 35, top_y + 46], radius=14, fill="#1e3a8a")
    draw.rectangle([c3_x0, top_y + 26, c3_x0 + col_w + 35, top_y + 46], fill="#1e3a8a")
    draw.text((c3_x0 + 15, top_y + 12), "📌 SECTOR & WATCHLIST", fill="#60a5fa", font=font_section)
    
    c3_items = [
        ("IDXENERGY", "+1.42%", True),
        ("IDXTECHNO", "+2.15%", True),
        ("IDXFINANCE", "+0.85%", True),
        ("IDXBASIC", "-0.34%", False),
    ]
    ry = top_y + 60
    for s_name, s_chg, s_pos in c3_items:
        draw.text((c3_x0 + 15, ry), s_name, fill="#e2e8f0", font=font_bold)
        chg_col = "#22c55e" if s_pos else "#ef4444"
        draw.text((c3_x0 + col_w - 20, ry), s_chg, fill=chg_col, font=font_badge)
        ry += 36
        
    draw.line([(c3_x0 + 15, ry + 10), (c3_x0 + col_w + 20, ry + 10)], fill="#374151", width=1)
    ry += 25
    draw.text((c3_x0 + 15, ry), "GLOBAL MACRO & ASING", fill="#38bdf8", font=font_bold)
    ry += 30
    draw.text((c3_x0 + 15, ry), "• Brent Oil: $82.40 (+0.65%)", fill="#94a3b8", font=font_regular)
    draw.text((c3_x0 + 15, ry + 25), "• Gold: $2,645 (+1.12%)", fill="#94a3b8", font=font_regular)
    draw.text((c3_x0 + 15, ry + 50), "• Foreign Flow: +Rp 428B (Net Buy)", fill="#4ade80", font=font_regular)
    
    ry += 95
    draw.line([(c3_x0 + 15, ry), (c3_x0 + col_w + 20, ry)], fill="#374151", width=1)
    ry += 15
    draw.text((c3_x0 + 15, ry), "🎯 TECHNICAL WATCHLIST", fill="#facc15", font=font_bold)
    ry += 30
    draw.text((c3_x0 + 15, ry), "1. BBRI: Breakout 5,100", fill="#e2e8f0", font=font_regular)
    draw.text((c3_x0 + 15, ry + 25), "2. MEDC: Rally katalis energi", fill="#e2e8f0", font=font_regular)
    draw.text((c3_x0 + 15, ry + 50), "3. ASII: Support bounce 4,800", fill="#e2e8f0", font=font_regular)
    
    _draw_footer(draw, W, H)
    img.save(output_path, "PNG", quality=95)
    return os.path.abspath(output_path)

def generate_market_card(normalized_data: dict, output_path: str = "logs/market_card.png", card_style: str = "1") -> str:
    """
    Renders market card with support for 3 distinct styles:
    - style "1": Standard IHSG & Top Gainers/Losers (Angka IHSG komposit putih)
    - style "2": Sector & Macro Radar Card
    - style "3": All-in-One Executive Dashboard
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    style_str = str(card_style).strip()
    if style_str == "2":
        return generate_card_v2(normalized_data, output_path)
    elif style_str == "3":
        return generate_card_v3(normalized_data, output_path)
    else:
        return generate_card_v1(normalized_data, output_path)
