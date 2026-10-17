#!/usr/bin/env python3
"""손으로 그린 노트 스케치 풍 썸네일 생성기.

usage: python3 _tools/sketch.py spec.json out.jpg

spec 형식은 _tools/README.md 참고. 순수 Pillow만 사용한다.
"""
import sys, os, json, math, random, zlib
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

W, H = 1200, 675          # 최종 해상도
S = 2                     # 슈퍼샘플링 배율
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(HERE, 'NanumPenScript-Regular.ttf')
INK = (33, 37, 50)
PAPER = (243, 239, 228)
MARKERS = {
    'yellow': (255, 224, 92), 'pink': (255, 182, 196),
    'green': (176, 226, 164), 'blue': (166, 204, 242), 'orange': (255, 200, 130),
}


class Sketch(object):
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.ink = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.ink)
        self.hl = Image.new('RGB', (W * S, H * S), (255, 255, 255))
        self.hd = ImageDraw.Draw(self.hl)
        self._fonts = {}

    # ---------- 기본 도구 ----------
    def font(self, size):
        key = int(round(size * S))
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(FONT_PATH, key)
        return self._fonts[key]

    def noise(self, n, scale):
        k = int(n / float(scale)) + 3
        c = [self.rng.uniform(-1, 1) for _ in range(k)]
        out = []
        for i in range(n):
            t = i / float(scale)
            i0 = int(t)
            f = (1 - math.cos(math.pi * (t - i0))) / 2.0
            out.append(c[i0] * (1 - f) + c[i0 + 1] * f)
        return out

    @staticmethod
    def resample(pts, step):
        out = [pts[0]]
        for a, b in zip(pts[:-1], pts[1:]):
            dist = math.hypot(b[0] - a[0], b[1] - a[1])
            n = max(1, int(dist / step))
            for i in range(1, n + 1):
                t = i / float(n)
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        return out

    def stroke(self, pts, width=4.4, amp=1.6, alpha=232, step=9):
        """흔들리는 펜선 한 줄."""
        pts = self.resample(pts, step)
        n = len(pts)
        if n < 2:
            return
        nz = self.noise(n, 5)
        nw = self.noise(n, 4)
        moved = []
        for i, (x, y) in enumerate(pts):
            j0, j1 = max(0, i - 1), min(n - 1, i + 1)
            dx, dy = pts[j1][0] - pts[j0][0], pts[j1][1] - pts[j0][1]
            ln = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / ln, dx / ln
            moved.append((x + nx * nz[i] * amp, y + ny * nz[i] * amp))
        col = tuple(int(c + self.rng.uniform(-6, 6)) for c in INK) + (alpha,)
        for i in range(n - 1):
            w = max(1.0, width * (0.84 + 0.3 * nw[i]))
            a, b = moved[i], moved[i + 1]
            self.d.line([a[0] * S, a[1] * S, b[0] * S, b[1] * S], fill=col, width=int(w * S))
            r = w * S / 2.0
            self.d.ellipse([b[0] * S - r, b[1] * S - r, b[0] * S + r, b[1] * S + r], fill=col)
        r = max(1.0, width * 0.9) * S / 2.0
        a = moved[0]
        self.d.ellipse([a[0] * S - r, a[1] * S - r, a[0] * S + r, a[1] * S + r], fill=col)

    def line(self, a, b, width=4.4, over=5):
        for k in range(2):
            ox = self.rng.uniform(-over, over)
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dy) or 1.0
            ux, uy = dx / ln, dy / ln
            s = self.rng.uniform(-2, over)
            e = self.rng.uniform(-2, over)
            p = (a[0] - ux * s, a[1] - uy * s)
            q = (b[0] + ux * e, b[1] + uy * e)
            jit = 1.6 if k == 0 else 2.4
            self.stroke([(p[0], p[1] + (0 if k == 0 else ox * 0.3)), q],
                        width=width if k == 0 else width * 0.62, amp=jit,
                        alpha=235 if k == 0 else 150)

    def rect(self, x, y, w, h, width=4.4):
        j = lambda: self.rng.uniform(-3, 3)
        c = [(x + j(), y + j()), (x + w + j(), y + j()), (x + w + j(), y + h + j()), (x + j(), y + h + j())]
        for i in range(4):
            self.line(c[i], c[(i + 1) % 4], width=width, over=7)

    def ellipse(self, cx, cy, rx, ry, width=4.4):
        for k in range(2):
            t0 = self.rng.uniform(0, 2 * math.pi)
            span = 2 * math.pi * self.rng.uniform(1.03, 1.09)
            n = 46
            nz = self.noise(n + 1, 6)
            pts = []
            for i in range(n + 1):
                t = t0 + span * i / float(n)
                k_r = 1 + 0.025 * nz[i] + (0.012 * i / n)
                pts.append((cx + math.cos(t) * rx * k_r, cy + math.sin(t) * ry * k_r))
            self.stroke(pts, width=width if k == 0 else width * 0.6, amp=1.2,
                        alpha=235 if k == 0 else 145, step=14)

    def poly(self, pts, closed=False, width=4.4):
        pts = list(pts)
        if closed:
            pts.append(pts[0])
        for i in range(len(pts) - 1):
            self.line(pts[i], pts[i + 1], width=width, over=3)

    def curve(self, pts, width=4.4):
        """부드러운 자유 곡선 (점들을 지나가는 Catmull-Rom)."""
        P = [pts[0]] + list(pts) + [pts[-1]]
        out = []
        for i in range(1, len(P) - 2):
            p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
            for k in range(12):
                t = k / 12.0
                t2, t3 = t * t, t * t * t
                out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t +
                                       (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 +
                                       (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
        out.append(P[-2])
        self.stroke(out, width=width, amp=1.3)
        self.stroke(out, width=width * 0.6, amp=2.0, alpha=140)

    def arrow(self, a, b, curve=0.14, width=4.4, head=28):
        mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
        dx, dy = b[0] - a[0], b[1] - a[1]
        dist = math.hypot(dx, dy) or 1.0
        c = (mx - dy / dist * dist * curve, my + dx / dist * dist * curve)
        pts = []
        for i in range(21):
            t = i / 20.0
            pts.append(((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0],
                        (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1]))
        self.stroke(pts, width=width, amp=1.3)
        ex, ey = pts[-1]
        px, py = pts[-3]
        ang = math.atan2(ey - py, ex - px)
        for sgn in (-1, 1):
            aa = ang + math.pi + sgn * math.radians(self.rng.uniform(24, 33))
            ll = head * self.rng.uniform(0.85, 1.1)
            self.stroke([(ex, ey), (ex + math.cos(aa) * ll, ey + math.sin(aa) * ll)], width=width, amp=0.8)
        return pts[len(pts) // 2]

    def figure(self, x, y, s=1.0, width=4.4):
        """막대 인간. (x, y)는 발 위치."""
        self.ellipse(x, y - 62 * s, 11 * s, 12 * s, width=width)
        self.line((x, y - 50 * s), (x, y - 22 * s), width=width, over=2)
        self.poly([(x - 17 * s, y - 33 * s), (x, y - 44 * s), (x + 17 * s, y - 33 * s)], width=width)
        self.line((x, y - 22 * s), (x - 12 * s, y), width=width, over=2)
        self.line((x, y - 22 * s), (x + 12 * s, y), width=width, over=2)

    def hatch(self, x, y, w, h, gap=13, width=3.0):
        off = -h
        while off < w:
            t0, t1 = max(0, -off), min(h, w - off)
            if t1 > t0 + 3:
                self.stroke([(x + off + t0, y + h - t0), (x + off + t1, y + h - t1)],
                            width=width, amp=1.0, alpha=190)
            off += gap + self.rng.uniform(-2, 2)

    def scribble(self, cx, cy, rx, ry, gap=7, width=3.6):
        """타원 안을 가로선으로 빽빽하게 칠한다 (까만 물체 표현)."""
        yy = -ry + 4
        while yy < ry - 2:
            hw = rx * math.sqrt(max(0.0, 1 - (yy / float(ry)) ** 2)) - 2
            if hw > 4:
                self.stroke([(cx - hw, cy + yy), (cx + hw, cy + yy + self.rng.uniform(-2, 2))],
                            width=width, amp=1.0, alpha=225)
            yy += gap + self.rng.uniform(-1.5, 1.5)

    def sun(self, x, y, r, width=4.4):
        self.ellipse(x, y, r, r, width=width)
        for i in range(10):
            a = i * math.pi / 5 + self.rng.uniform(-0.08, 0.08)
            self.stroke([(x + math.cos(a) * (r + 10), y + math.sin(a) * (r + 10)),
                         (x + math.cos(a) * (r + 10 + r * 0.7), y + math.sin(a) * (r + 10 + r * 0.7))],
                        width=width, amp=0.8)

    def squiggle(self, x, y, w, width=3.6):
        pts = []
        n = max(4, int(w / 14))
        for i in range(n + 1):
            pts.append((x + w * i / float(n), y + (4 if i % 2 else -4)))
        self.stroke(pts, width=width, amp=1.0, step=6)

    # ---------- 글자 ----------
    def measure(self, s, size):
        f = self.font(size)
        return sum(f.getsize(ch)[0] * 0.93 if ch != ' ' else f.getsize('가')[0] * 0.33 for ch in s) / float(S)

    def wrap(self, text, size, max_w):
        lines = []
        for para in text.split('\n'):
            words = para.split(' ')
            cur = ''
            for wd in words:
                trial = (cur + ' ' + wd) if cur else wd
                if self.measure(trial, size) <= max_w:
                    cur = trial
                    continue
                if cur:
                    lines.append(cur)
                    cur = ''
                if self.measure(wd, size) <= max_w:
                    cur = wd
                else:
                    piece = ''
                    for ch in wd:
                        if self.measure(piece + ch, size) <= max_w:
                            piece += ch
                        else:
                            lines.append(piece)
                            piece = ch
                    cur = piece
            lines.append(cur)
        return lines

    def fit(self, text, max_w, max_h, start=54, lo=22, lh=1.1):
        size = start
        while size > lo:
            lines = self.wrap(text, size, max_w)
            if len(lines) * size * lh <= max_h:
                return size, lines
            size -= 2
        return lo, self.wrap(text, lo, max_w)

    def _blit(self, im, x, y):
        x, y = int(x), int(y)
        bx0, by0 = max(0, x), max(0, y)
        bx1, by1 = min(self.ink.size[0], x + im.size[0]), min(self.ink.size[1], y + im.size[1])
        if bx1 <= bx0 or by1 <= by0:
            return
        part = im.crop((bx0 - x, by0 - y, bx1 - x, by1 - y))
        base = self.ink.crop((bx0, by0, bx1, by1))
        self.ink.paste(Image.alpha_composite(base, part), (bx0, by0))

    def glyph_line(self, s, x, y, size, color=INK):
        """한 줄 그리기. (x, y)는 줄의 왼쪽 위. 너비 반환."""
        f = self.font(size)
        cx = x * S
        slope = self.rng.uniform(-0.014, 0.014)
        x0 = cx
        for ch in s:
            if ch == ' ':
                cx += f.getsize('가')[0] * 0.33
                continue
            gw, gh = f.getsize(ch)
            pad = int(size * S * 0.4)
            im = Image.new('RGBA', (gw + pad * 2, gh + pad * 2), (0, 0, 0, 0))
            col = tuple(int(c + self.rng.uniform(-8, 8)) for c in color) + (self.rng.randint(222, 246),)
            ImageDraw.Draw(im).text((pad, pad), ch, font=f, fill=col, stroke_width=int(size * S / 60.0) + 1, stroke_fill=col)
            im = im.rotate(self.rng.uniform(-3.2, 3.2), resample=Image.BICUBIC, expand=False)
            dy = self.rng.uniform(-0.035, 0.035) * size * S + (cx - x0) * slope
            self._blit(im, cx - pad, y * S + dy - pad)
            cx += gw * 0.93 + self.rng.uniform(-0.8, 1.2)
        return cx / S - x

    def marker(self, x, y, w, h, color):
        col = MARKERS.get(color, MARKERS['yellow'])
        col = tuple(int(255 - (255 - c) * 0.72) for c in col)
        for k in range(2):
            sk = self.rng.uniform(-5, 5)
            j = lambda: self.rng.uniform(-3, 3)
            pts = [(x - 6 + j() + sk, y + h * 0.18 + j() + k * 3), (x + w + 8 + j(), y + h * 0.1 + j() + k * 3),
                   (x + w + 4 + j(), y + h * 0.95 + j()), (x - 8 + j(), y + h + j() + k * 2)]
            self.hd.polygon([(px * S, py * S) for px, py in pts], fill=col)

    def text(self, s, x, y, size=40, w=None, h=None, align='left', hl=None, color=INK, lh=1.1):
        """블록 글자. w를 주면 자동 줄바꿈 + 글자 크기 자동 축소."""
        if w:
            size, lines = self.fit(s, w, h or 9999, start=size, lh=lh)
        else:
            lines = s.split('\n')
        yy = y
        for ln in lines:
            lw = self.measure(ln, size)
            if align == 'center' and w:
                xx = x + (w - lw) / 2.0
            elif align == 'center':
                xx = x - lw / 2.0
            else:
                xx = x
            if hl:
                self.marker(xx, yy + size * 0.18, lw, size * 0.7, hl)
            self.glyph_line(ln, xx, yy, size, color)
            yy += size * lh
        return size, yy - y

    # ---------- 합성 ----------
    def render(self, out):
        rng = random.Random(7)
        big = (W * S, H * S)
        paper = Image.new('RGB', big, PAPER)
        grain = Image.effect_noise(big, 9).convert('RGB')
        paper = ImageChops.add(paper, grain, 1.0, -128)
        blotch = Image.effect_noise((W // 70, H // 70), 5).resize(big, Image.BICUBIC).convert('RGB')
        paper = ImageChops.add(paper, blotch, 1.0, -128)
        vg = Image.radial_gradient('L').resize(big, Image.BICUBIC).point(lambda v: int(v * 0.16))
        paper = ImageChops.subtract(paper, Image.merge('RGB', (vg, vg, vg)))
        paper = ImageChops.multiply(paper, self.hl.filter(ImageFilter.GaussianBlur(S * 0.7)))
        ink = self.ink.filter(ImageFilter.GaussianBlur(S * 0.45))
        base = paper.convert('RGBA')
        base.alpha_composite(ink)
        img = base.convert('RGB').resize((W, H), Image.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(0.35))
        fine = Image.effect_noise((W, H), 7).convert('RGB')
        img = ImageChops.add(img, fine, 1.0, -128)
        img.save(out, 'JPEG', quality=88, optimize=True, progressive=True)


# ---------- 템플릿 ----------
def title_block(sk, spec):
    y0 = 56
    t = spec.get('title')
    if t:
        size, h = sk.text(t, 70, 30, size=92)
        tw = sk.measure(t, size)
        sk.line((70, 30 + size * 1.0), (70 + tw + 14, 30 + size * 0.98), width=4.6, over=4)
        y0 = 30 + size * 1.2 + 22
    return y0


def node(sk, n, x, y, w, h, shape='rect'):
    if isinstance(n, str):
        n = {'text': n}
    if shape == 'ellipse':
        sk.ellipse(x + w / 2.0, y + h / 2.0, w / 2.0, h / 2.0)
    else:
        sk.rect(x, y, w, h)
    if not n.get('text'):
        return
    sub = n.get('sub')
    inner_w = w - 36 if shape == 'rect' else w * 0.72
    inner_h = h - 24 if shape == 'rect' else h * 0.66
    th = inner_h * (0.62 if sub else 1.0)
    size, used = sk.fit(n['text'], inner_w, th, start=n.get('size', 72))
    lines = sk.wrap(n['text'], size, inner_w)
    total = len(lines) * size * 1.1
    ty = y + (h - (total + ((sk.fit(sub, inner_w, inner_h * 0.34, start=56)[0] * 1.1 + 6) if sub else 0))) / 2.0
    sz, hh = sk.text(n['text'], x + (w - inner_w) / 2.0, ty, size=size, w=inner_w, h=th, align='center', hl=n.get('hl'))
    if sub:
        sk.text(sub, x + (w - inner_w) / 2.0, ty + hh + 4, size=56, w=inner_w, h=inner_h * 0.34, align='center')


def t_flow(sk, spec):
    y0 = title_block(sk, spec)
    nodes = spec['nodes']
    n = len(nodes)
    cols = n if n <= 4 else int(math.ceil(n / 2.0))
    rows = int(math.ceil(n / float(cols)))
    bottom = H - (96 if spec.get('caption') else 54)
    aw, ah = W - 140, bottom - y0
    gap = 96
    bw = (aw - gap * (cols - 1)) / float(cols)
    bh = min((ah - 56 * (rows - 1)) / rows, 230)
    edges = spec.get('edges', [])
    pos = []
    for i, nd in enumerate(nodes):
        r, c = divmod(i, cols)
        x = 70 + c * (bw + gap)
        y = y0 + (ah - (bh * rows + 56 * (rows - 1))) / 2.0 + r * (bh + 56)
        node(sk, nd, x, y, bw, bh)
        pos.append((x, y))
    for i in range(n - 1):
        (x1, y1), (x2, y2) = pos[i], pos[i + 1]
        if y1 == y2:
            mid = sk.arrow((x1 + bw + 6, y1 + bh / 2.0), (x2 - 8, y2 + bh / 2.0), curve=0.12)
            lab = edges[i] if i < len(edges) else None
            if lab:
                sk.text(lab, mid[0] - (gap + 40) / 2.0, mid[1] - 62, size=56, w=gap + 40, h=64, align='center')
        else:
            sk.arrow((x1 + bw / 2.0, y1 + bh + 6), (x2 + bw / 2.0, y2 - 8), curve=-0.25)
    if spec.get('caption'):
        sk.text(spec['caption'], 70, H - 92, size=54, w=W - 140, h=70, align='center')


def t_versus(sk, spec):
    y0 = title_block(sk, spec)
    bottom = H - (96 if spec.get('caption') else 54)
    colw = (W - 140 - 120) / 2.0
    for k, side in enumerate(('left', 'right')):
        sd = spec[side]
        x = 70 + k * (colw + 120)
        sk.text(sd['title'], x, y0, size=78, w=colw, h=92, align='center', hl=sd.get('hl'))
        sk.line((x + 20, y0 + 86), (x + colw - 20, y0 + 84), width=3.6)
        items = sd.get('items', [])
        avail = bottom - (y0 + 112)
        per = avail / max(1, len(items))
        yy = y0 + 112
        for it in items:
            size, used = sk.fit(it, colw - 54, min(per - 8, 150), start=64)
            sk.ellipse(x + 14, yy + size * 0.62, 6, 6, width=4)
            _, hh = sk.text(it, x + 38, yy, size=size, w=colw - 54, h=min(per - 8, 150))
            yy += max(per, hh + 8)
    mx = 70 + colw + 60
    sk.line((mx, y0 + 20), (mx, bottom - 6), width=3.2, over=8)
    sk.ellipse(mx, (y0 + bottom) / 2.0, 52, 38)
    sk.text(spec.get('vs', 'vs'), mx, (y0 + bottom) / 2.0 - 30, size=60, align='center')
    if spec.get('caption'):
        sk.text(spec['caption'], 70, H - 92, size=54, w=W - 140, h=70, align='center')


def t_hub(sk, spec):
    y0 = title_block(sk, spec)
    bottom = H - (96 if spec.get('caption') else 50)
    cx, cy = W / 2.0, (y0 + bottom) / 2.0
    c = spec['center']
    if isinstance(c, str):
        c = {'text': c}
    cw, chh = 280, 130
    nodes = spec['nodes']
    n = len(nodes)
    nw, nh = 270, 108
    rx, ry = 410, (bottom - y0) / 2.0 - nh / 2.0 - 6
    off = 0.5 if n % 2 == 0 else 0.0
    for i, nd in enumerate(nodes):
        if isinstance(nd, str):
            nd = {'text': nd}
        ang = -math.pi / 2 + 2 * math.pi * (i + off) / n
        px, py = cx + math.cos(ang) * rx, cy + math.sin(ang) * ry
        dx, dy = px - cx, py - cy
        ln = math.hypot(dx, dy) or 1.0
        ux, uy = dx / ln, dy / ln
        # 중앙 타원 경계 / 노드 사각형 경계에서 선을 끊는다
        k1 = 1.0 / math.sqrt((ux / (cw / 2.0)) ** 2 + (uy / (chh / 2.0)) ** 2)
        k2 = min((nw / 2.0) / abs(ux) if abs(ux) > 1e-6 else 1e9, (nh / 2.0) / abs(uy) if abs(uy) > 1e-6 else 1e9)
        a = (cx + ux * (k1 + 8), cy + uy * (k1 + 8))
        b = (px - ux * (k2 + 8), py - uy * (k2 + 8))
        if spec.get('arrows'):
            mid = sk.arrow(a, b, curve=0.06)
        else:
            sk.line(a, b, width=4.0)
            mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        if nd.get('edge'):
            sk.text(nd['edge'], mid[0] - 80, mid[1] - 30, size=46, w=160, h=56, align='center')
        node(sk, nd, px - nw / 2.0, py - nh / 2.0, nw, nh, shape='ellipse' if nd.get('round') else 'rect')
    node(sk, c, cx - cw / 2.0, cy - chh / 2.0, cw, chh, shape='ellipse')
    if spec.get('caption'):
        sk.text(spec['caption'], 70, H - 92, size=54, w=W - 140, h=70, align='center')


def t_free(sk, spec):
    y0 = title_block(sk, spec)
    for e in spec.get('elements', []):
        t = e['type']
        if t == 'box':
            node(sk, e, e['x'], e['y'], e['w'], e['h'])
        elif t == 'ellipse':
            if e.get('text'):
                node(sk, e, e['x'], e['y'], e['w'], e['h'], shape='ellipse')
            else:
                sk.ellipse(e['x'] + e['w'] / 2.0, e['y'] + e['h'] / 2.0, e['w'] / 2.0, e['h'] / 2.0)
        elif t == 'line':
            sk.line(tuple(e['from']), tuple(e['to']), width=e.get('width', 3.2))
        elif t == 'arrow':
            mid = sk.arrow(tuple(e['from']), tuple(e['to']), curve=e.get('curve', 0.14))
            if e.get('label'):
                sk.text(e['label'], mid[0] - 95, mid[1] - 62, size=58, w=190, h=64, align='center')
        elif t == 'text':
            sk.text(e['text'], e['x'], e['y'], size=e.get('size', 56), w=e.get('w'), h=e.get('h'),
                    align=e.get('align', 'left'), hl=e.get('hl'))
        elif t == 'figure':
            sk.figure(e['x'], e['y'], e.get('s', 1.0))
            if e.get('label'):
                sk.text(e['label'], e['x'], e['y'] + 6, size=60, align='center')
        elif t == 'hatch':
            sk.hatch(e['x'], e['y'], e['w'], e['h'], gap=e.get('gap', 11))
        elif t == 'scribble':
            sk.scribble(e['x'], e['y'], e['rx'], e['ry'], gap=e.get('gap', 7))
        elif t == 'sun':
            sk.sun(e['x'], e['y'], e.get('r', 34))
        elif t == 'poly':
            sk.poly([tuple(p) for p in e['points']], closed=e.get('closed', False))
        elif t == 'curve':
            sk.curve([tuple(p) for p in e['points']])
        elif t == 'squiggle':
            sk.squiggle(e['x'], e['y'], e['w'])
    if spec.get('caption'):
        sk.text(spec['caption'], 70, H - 92, size=54, w=W - 140, h=70, align='center')


TEMPLATES = {'flow': t_flow, 'versus': t_versus, 'hub': t_hub, 'free': t_free}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    spec = json.load(open(sys.argv[1], encoding='utf-8'))
    out = sys.argv[2]
    seed = zlib.crc32(os.path.basename(out).encode('utf-8')) & 0xffffffff
    sk = Sketch(seed)
    TEMPLATES[spec.get('template', 'free')](sk, spec)
    sk.render(out)
    print('ok')


if __name__ == '__main__':
    main()
