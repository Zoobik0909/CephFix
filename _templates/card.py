"""Квадратная карточка статьи 1080×1080 (JPEG) для Instagram, LinkedIn и превью ссылок."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = HERE / 'fonts'
S = 1080
BG = (14, 17, 22)
PANEL = (19, 24, 32)
LINE = (34, 42, 52)
TX = (245, 247, 250)
TX2 = (174, 183, 194)
TX3 = (138, 147, 160)
ACCENT = (127, 168, 212)

TEXT = {
    'ru': {'eyebrow': 'ЦЕФАЛОМЕТРИЯ · СТАТЬЯ', 'site': 'cephfix.com/articles', 'cta': 'Программа CephFix — 7 дней бесплатно'},
    'en': {'eyebrow': 'CEPHALOMETRY · ARTICLE', 'site': 'cephfix.com/en/articles', 'cta': 'CephFix software — free for 7 days'},
}


def _font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def _wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ''
    for w in words:
        trial = (cur + ' ' + w).strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit(draw, text, name, sizes, width, max_lines):
    for size in sizes:
        f = _font(name, size)
        lines = _wrap(draw, text, f, width)
        if len(lines) <= max_lines:
            return f, lines
    f = _font(name, sizes[-1])
    lines = _wrap(draw, text, f, width)[:max_lines]
    lines[-1] = lines[-1].rstrip(' .,:;—') + '…'
    return f, lines


def make_card(lang, title, desc, out_path, logo_path=None):
    t = TEXT[lang]
    img = Image.new('RGB', (S, S), BG)
    d = ImageDraw.Draw(img)
    M = 84
    W = S - 2 * M

    # рамка-панель
    d.rounded_rectangle((40, 40, S - 40, S - 40), radius=36, fill=PANEL, outline=LINE, width=2)

    # логотип и название
    y = 104
    x = M
    if logo_path and Path(logo_path).exists():
        logo = Image.open(logo_path).convert('RGBA').resize((76, 76), Image.LANCZOS)
        img.paste(logo, (x, y), logo)
        x += 76 + 22
    brand = _font('InterDisplay-Bold.otf', 44)
    d.text((x, y + 38), 'CephFix', font=brand, fill=TX, anchor='lm')

    # надзаголовок
    y = 250
    eb = _font('Inter-Medium.otf', 26)
    d.text((M, y), t['eyebrow'], font=eb, fill=ACCENT)
    d.line((M, y + 52, M + 90, y + 52), fill=ACCENT, width=4)

    # заголовок и описание: подбираем размеры так, чтобы всё влезло над нижней линией
    top = y + 92
    limit = S - 190 - 40
    layout = None
    for tsize in (84, 76, 68, 62, 56, 50):
        tf = _font('InterDisplay-Bold.otf', tsize)
        tlines = _wrap(d, title, tf, W)
        if len(tlines) > 5:
            continue
        th = len(tlines) * int(tsize * 1.14)
        for dsize in (34, 31, 28):
            df = _font('Inter-Regular.otf', dsize)
            dl = _wrap(d, desc, df, W)
            room = (limit - (top + th + 34)) // int(dsize * 1.4)
            if room >= len(dl):
                layout = (tf, tlines, df, dl)
                break
            if room >= 2 and dsize == 28 and tsize <= 56:
                dl = dl[:room]
                dl[-1] = dl[-1].rstrip(' .,:;—') + '…'
                layout = (tf, tlines, df, dl)
                break
        if layout:
            break
    if layout is None:
        tf, tlines = _fit(d, title, 'InterDisplay-Bold.otf', [56, 50], W, 5)
        df, dl = _font('Inter-Regular.otf', 28), []
        layout = (tf, tlines, df, dl)
    tf, tlines, df, dlines = layout
    y = top
    for line in tlines:
        d.text((M, y), line, font=tf, fill=TX)
        y += int(tf.size * 1.14)
    y += 34
    for line in dlines:
        d.text((M, y), line, font=df, fill=TX2)
        y += int(df.size * 1.4)

    # низ
    d.line((M, S - 190, S - M, S - 190), fill=LINE, width=2)
    cta = _font('Inter-Medium.otf', 30)
    d.text((M, S - 150), t['cta'], font=cta, fill=TX)
    site = _font('Inter-Regular.otf', 28)
    d.text((M, S - 104), t['site'], font=site, fill=ACCENT)

    img.save(out_path, 'JPEG', quality=90, optimize=True, progressive=True)
    return out_path
