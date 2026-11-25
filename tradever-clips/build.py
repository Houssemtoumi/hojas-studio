import os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

S = '/tmp/claude-0/-home-user-hojas-studio/becfd0c3-59c3-5c10-b34b-3250a4c23bf6/scratchpad'
SRC = S + '/src'
OUT = sys.argv[1]
GFX = S + '/gfx'
os.makedirs(GFX, exist_ok=True); os.makedirs(OUT, exist_ok=True)
W, H = 1080, 1920
WIN_Y, WIN_H = 340, 1240
GREEN = (74, 222, 58)
FB = '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'
FM = '/usr/share/fonts/opentype/inter/Inter-SemiBold.otf'

def src(n):
    for f in os.listdir(SRC):
        if n in f: return os.path.join(SRC, f)
    raise SystemExit(n)

# ---------- brand banner (logo from Tradever's own end card) ----------
def banner():
    card = Image.open(S + '/fr/endcard.png').convert('RGB').crop((100, 555, 620, 720))
    px = card.load(); w, h = card.size
    logo = Image.new('RGBA', card.size)
    lp = logo.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            a = max(0, min(255, int((max(r, g, b) - 22) * 255 / 200)))
            lp[x, y] = (r, g, b, a)
    logo = logo.resize((int(w * 0.62), int(h * 0.62)), Image.LANCZOS)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cy = 1665
    lx = (W - logo.width) // 2
    im.alpha_composite(logo, (lx, cy - logo.height // 2))
    # fading green rules either side
    for side in (0, 1):
        x0, x1 = (40, lx - 20) if side == 0 else (lx + logo.width + 20, W - 40)
        for x in range(x0, x1):
            t = (x - x0) / max(1, x1 - x0)
            a = int(255 * (t if side == 0 else 1 - t))
            d.line([(x, cy), (x, cy + 2)], fill=GREEN + (a,))
    f = ImageFont.truetype(FM, 22)
    parts = [('USE PROMO CODE ', (200, 200, 200)), ('LAYTH', GREEN), ('   |   GET 40% OFF AN ACCOUNT', (200, 200, 200))]
    tw = sum(d.textlength(p, font=f) for p, _ in parts)
    x = (W - tw) / 2
    for p, c in parts:
        d.text((x, cy + logo.height // 2 + 14), p, font=f, fill=c + (255,)); x += d.textlength(p, font=f)
    return im

BANNER = banner()

def header(text, path):
    """text: lines separated by \n; [word] = green accent."""
    im = BANNER.copy()
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FB, 54)
    lines = []
    for raw in text.split('\n'):
        toks = re.findall(r'\[[^\]]+\]|\S+', raw)
        words = []
        for t in toks:
            if t.startswith('['):
                words += [(w, True) for w in t[1:-1].split()]
            else:
                words.append((t, False))
        cur = []
        for w in words:
            trial = ' '.join(x for x, _ in cur + [w])
            if cur and d.textlength(trial, font=f) > 960:
                lines.append(cur); cur = []
            cur.append(w)
        lines.append(cur)
    lh = 68
    y = WIN_Y - 36 - lh * len(lines)
    sp = d.textlength(' ', font=f)
    for ln in lines:
        tw = sum(d.textlength(w, font=f) for w, _ in ln) + sp * (len(ln) - 1)
        x = (W - tw) / 2
        for w, g in ln:
            d.text((x, y), w, font=f, fill=(GREEN if g else (255, 255, 255)) + (255,))
            x += d.textlength(w, font=f) + sp
        y += lh
    im.save(path)

def render(name, head, segs, audio, total):
    png = f'{GFX}/{name}.png'
    header(head, png)
    inputs, filt, labels = [], [], []
    for i, s in enumerate(segs):
        f, ss, dur, mode = s[:4]
        inputs += ['-ss', str(ss), '-t', str(dur), '-i', src(f)]
        if mode == 'v':
            yfrac = s[4]  # top of window in the 1080-wide scaled source, as fraction of its height
            filt.append(f'[{i}:v]scale=1080:-2,setsar=1,crop=1080:{WIN_H}:0:min(ih-{WIN_H}\\,ih*{yfrac}),fps=30,format=yuv420p[s{i}]')
        else:  # band: x,y,w,h in source px
            x, y, w, h = s[4]
            filt.append(f'[{i}:v]crop={w}:{h}:{x}:{y},scale=1080:-2,setsar=1,pad=1080:{WIN_H}:0:(oh-ih)/2:black,fps=30,format=yuv420p[s{i}]')
        labels.append(f'[s{i}]')
    n = len(segs)
    filt.append(''.join(labels) + f'concat=n={n}:v=1:a=0[win]')
    filt.append(f'color=black:s={W}x{H}:r=30:d={total}[bg]')
    filt.append(f'[bg][win]overlay=0:{WIN_Y}:shortest=1[b1]')
    ai = n
    inputs += ['-loop', '1', '-t', str(total), '-i', png]
    filt.append(f'[b1][{n}:v]overlay=0:0:shortest=1,format=yuv420p[v]')
    af, ass = audio
    inputs += ['-ss', str(ass), '-t', str(total), '-i', src(af)]
    filt.append(f'[{n+1}:a]aresample=48000,afade=t=in:d=0.05,afade=t=out:st={total-0.6}:d=0.6,loudnorm=I=-14:TP=-1.5:LRA=11[a]')
    out = f'{OUT}/{name}.mp4'
    cmd = ['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(filt), '-map', '[v]', '-map', '[a]',
           '-t', str(total), '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)
    print('ok', out)

L = lambda i: i  # id fragments
JOBS = {
 '01-ceo-pays-out': ("POV: Your prop firm CEO [actually pays out]",
    [('7703570622', 0, 5.5, 'v', 0.18), ('7684409906', 3.5, 6.5, 'v', 0.10)],
    ('7703570622', 0), 12.0),
 '02-switching-feels-like': ("How it feels after switching to [Tradever]",
    [('7690642897', 3.0, 14.0, 'band', (0, 437, 720, 405))],
    ('7690642897', 3.0), 14.0),
 '03-other-firms-vs-tradever': ("Trading with other prop firms\nvs trading with [Tradever]",
    [('7693956681', 0, 14.1, 'v', 0.04)],
    ('7693956681', 0), 14.1),
 '04-27k-day': ("POV: You hit a [$27K day] trading futures",
    [('7691348172', 0, 5.0, 'v', 0.25), ('7688432286', 0.5, 3.5, 'v', 0.04), ('7703990540', 12.5, 4.0, 'v', 0.30)],
    ('7691348172', 0), 12.5),
 '05-first-payout-rolex': ("Imagine your [first payout] buying this",
    [('7683555294', 0, 11.4, 'v', 0.24)],
    ('7683555294', 0), 11.4),
 '06-mom-real-job': ("Mom: \"get a real job\"\nMe after my first [Tradever payout:]",
    [('7684409906', 4.5, 2.5, 'v', 0.10), ('7697717127', 2.5, 10.0, 'v', 0.12)],
    ('7697717127', 0), 12.5),
}
only = sys.argv[2:] or list(JOBS)
for k in only:
    render(k, *JOBS[k])
