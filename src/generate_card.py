import os
import datetime
from PIL import Image, ImageDraw, ImageFont

def _get_font(size: int, bold: bool = False):
    """
    Attempts to load a clean TrueType font from system paths.
    Falls back to default bitmap font if no TTF is found.
    """
    candidate_fonts = [
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

def generate_market_card(normalized_data: dict, output_path: str = "logs/market_card.png") -> str:
    """
    Renders a high-resolution dark-mode market infographic card showing IHSG,
    Top Gainers, and Top Losers.
    
    Returns the absolute path to the generated PNG image.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Dimensions & Colors
    W, H = 1200, 750
    img = Image.new("RGB", (W, H), color="#0f172a")  # Slate 900
    draw = ImageDraw.Draw(img)
    
    # Fonts
    font_title = _get_font(34, bold=True)
    font_subtitle = _get_font(18, bold=False)
    font_section = _get_font(21, bold=True)
    font_row_bold = _get_font(20, bold=True)
    font_row = _get_font(19, bold=False)
    font_footer = _get_font(17, bold=False)
    font_ihsg_val = _get_font(28, bold=True)
    font_badge = _get_font(16, bold=True)
    
    # Top Header Background Accent
    draw.line([(0, 0), (W, 0)], fill="#38bdf8", width=6)
    
    # Header Left: Title & Subtitle
    draw.text((50, 35), "BRIEFIN", fill="#38bdf8", font=font_title)
    bbox_briefin = draw.textbbox((50, 35), "BRIEFIN", font=font_title)
    draw.text((bbox_briefin[2] + 12, 35), "• DAILY MARKET BRIEF", fill="#f1f5f9", font=font_title)
    
    today_str = datetime.datetime.now().strftime("%d %B %Y")
    draw.text((50, 80), f"IDX Market Pulse  |  {today_str}", fill="#94a3b8", font=font_subtitle)
    
    # Header Right: IHSG Badge Panel
    ihsg = normalized_data.get("ihsg", {})
    price = ihsg.get("price", "N/A")
    change = ihsg.get("change", 0)
    pct = ihsg.get("percent_change", 0)
    
    is_positive = (change >= 0) if isinstance(change, (int, float)) else True
    ihsg_color = "#22c55e" if is_positive else "#ef4444"
    direction_sign = "+" if is_positive else ""
    
    price_str = f"{price:,.2f}" if isinstance(price, (int, float)) else str(price)
    change_str = f"{direction_sign}{change:,.2f} ({direction_sign}{pct:.2f}%)" if isinstance(change, (int, float)) else f"{change} ({pct}%)"
    
    # IHSG Box (Right aligned)
    box_x0, box_y0, box_x1, box_y1 = 780, 28, 1150, 118
    draw.rounded_rectangle([box_x0, box_y0, box_x1, box_y1], radius=12, fill="#1e293b", outline="#334155", width=1)
    
    draw.text((box_x0 + 20, box_y0 + 12), "IHSG COMPOSITE", fill="#94a3b8", font=font_badge)
    draw.text((box_x0 + 20, box_y0 + 40), price_str, fill="#f8fafc", font=font_ihsg_val)
    
    # Measure change text to size badge precisely
    c_bbox = draw.textbbox((0, 0), change_str, font=font_badge)
    c_w = c_bbox[2] - c_bbox[0]
    badge_bg = "#14532d" if is_positive else "#7f1d1d"
    badge_x1 = box_x1 - 15
    badge_x0 = badge_x1 - c_w - 20
    badge_y0, badge_y1 = box_y0 + 42, box_y0 + 76
    draw.rounded_rectangle([badge_x0, badge_y0, badge_x1, badge_y1], radius=8, fill=badge_bg)
    draw.text((badge_x0 + 10, badge_y0 + 7), change_str, fill=ihsg_color, font=font_badge)
    
    # --- Two Columns: Gainers & Losers Panels ---
    panel_y0, panel_y1 = 145, 665
    left_x0, left_x1 = 50, 585
    right_x0, right_x1 = 615, 1150
    
    # Left: Top Gainers Panel
    draw.rounded_rectangle([left_x0, panel_y0, left_x1, panel_y1], radius=16, fill="#1e293b", outline="#334155", width=1)
    # Header bar
    draw.rounded_rectangle([left_x0, panel_y0, left_x1, panel_y0 + 55], radius=16, fill="#14532d")
    draw.rectangle([left_x0, panel_y0 + 35, left_x1, panel_y0 + 55], fill="#14532d")
    # Draw green dot indicator
    draw.ellipse([left_x0 + 25, panel_y0 + 22, left_x0 + 37, panel_y0 + 34], fill="#4ade80")
    draw.text((left_x0 + 48, panel_y0 + 16), "TOP 5 GAINERS", fill="#4ade80", font=font_section)
    
    # Right: Top Losers Panel
    draw.rounded_rectangle([right_x0, panel_y0, right_x1, panel_y1], radius=16, fill="#1e293b", outline="#334155", width=1)
    # Header bar
    draw.rounded_rectangle([right_x0, panel_y0, right_x1, panel_y0 + 55], radius=16, fill="#7f1d1d")
    draw.rectangle([right_x0, panel_y0 + 35, right_x1, panel_y0 + 55], fill="#7f1d1d")
    # Draw red dot indicator
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
    
    # Draw Gainers
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
            draw.text((badge_rect[0] + 12, cy + 14), f"+{pct_val:.2f}%", fill="#86efac", font=font_row_bold)
        else:
            draw.text((left_x0 + 75, cy + 12), "-", fill="#64748b", font=font_row)
            
    # Draw Losers
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
            draw.text((badge_rect[0] + 12, cy + 14), f"{pct_val:.2f}%", fill="#fca5a5", font=font_row_bold)
        else:
            draw.text((right_x0 + 75, cy + 12), "-", fill="#64748b", font=font_row)
            
    # --- Footer ---
    footer_y = 698
    draw.text((50, footer_y), "Automated by Briefin", fill="#94a3b8", font=font_footer)
    
    author_str = "Author: Albert & Einstein"
    auth_bbox = draw.textbbox((0, 0), author_str, font=font_footer)
    auth_w = auth_bbox[2] - auth_bbox[0]
    draw.text((W - 50 - auth_w, footer_y), author_str, fill="#38bdf8", font=font_footer)
    
    # Save Image
    img.save(output_path, "PNG", quality=95)
    return os.path.abspath(output_path)
