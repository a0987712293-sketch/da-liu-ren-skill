#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""大六壬排盤圖（PNG）。需要 Pillow 與任一 CJK 字型。"""
from __future__ import annotations

import glob
import os

from PIL import Image, ImageDraw, ImageFont

from liuren import Chart, GENERAL_NAME, TIANJIANG_SHORT, liuqin

# 式盤地盤固定位置（南上北下）：巳午未申 / 辰  酉 / 卯  戌 / 寅丑子亥
RING = {"巳": (0, 0), "午": (1, 0), "未": (2, 0), "申": (3, 0),
        "辰": (0, 1), "酉": (3, 1), "卯": (0, 2), "戌": (3, 2),
        "寅": (0, 3), "丑": (1, 3), "子": (2, 3), "亥": (3, 3)}

BG = (250, 246, 238)
INK = (38, 34, 30)
MUTED = (128, 118, 106)
LINE = (196, 184, 166)
RED = (168, 42, 36)
GOLD = (176, 128, 40)
PANEL = (243, 236, 223)
WX_COLOR = {"木": (46, 125, 72), "火": (186, 52, 42), "土": (150, 106, 40), "金": (120, 120, 128), "水": (34, 86, 156)}

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-*.ttc",
    "/usr/share/fonts/**/NotoSerifCJK*.ttc",
    "/usr/share/fonts/**/NotoSansCJK*.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/msjh.ttc",
    "C:/Windows/Fonts/mingliu.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]


def _font_path(bold: bool = False) -> str | None:
    env = os.environ.get("LIUREN_FONT")
    if env and os.path.exists(env):
        return env
    for pat in FONT_CANDIDATES:
        hits = sorted(glob.glob(pat, recursive=True))
        if bold:
            hits = sorted(hits, key=lambda h: ("Bold" not in h, h))
        else:
            hits = sorted(hits, key=lambda h: ("Regular" not in h, h))
        if hits:
            return hits[0]
    return None


class Fonts:
    def __init__(self):
        self.reg = _font_path(False)
        self.bold = _font_path(True) or self.reg
        if not self.reg:
            raise RuntimeError("找不到中文字型，請設定環境變數 LIUREN_FONT 指向 .ttf/.ttc 檔")
        self.cache = {}

    def __call__(self, size: int, bold: bool = False):
        key = (size, bold)
        if key not in self.cache:
            path = self.bold if bold else self.reg
            idx = 1 if path.endswith(".ttc") and "CJK" in path else 0  # Noto CJK .ttc：index 1 為 TC
            try:
                self.cache[key] = ImageFont.truetype(path, size, index=idx)
            except OSError:
                self.cache[key] = ImageFont.truetype(path, size)
        return self.cache[key]


def _center(d: ImageDraw.ImageDraw, xy, text, font, fill):
    x, y = xy
    d.text((x, y), text, font=font, fill=fill, anchor="mm")


def render_png(c: Chart, path: str, scale: float = 1.0) -> str:
    from liuren import wx
    F = Fonts()
    W = int(1000 * scale)
    S = lambda v: int(v * scale)
    H = S(1500)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # ---- 標題與資訊
    _center(d, (W // 2, S(56)), "大六壬課式", F(S(44), True), INK)
    cal = c.calendar
    y = S(108)
    lines = []
    if cal:
        lines.append(f"{cal['solar']}　農曆{cal['lunar']}")
        lines.append(f"{cal['year_gz']}年　{cal['month_gz']}月　{c.day_gz}日　{cal['hour_gz']}時")
        lines.append(f"月將 {c.general}（{GENERAL_NAME[c.general]}）・{cal['zhongqi']}後　占時 {c.hour_zhi}")
    else:
        lines.append(f"{c.day_gz}日　占時 {c.hour_zhi}　月將 {c.general}（{GENERAL_NAME[c.general]}）")
    lines.append(f"{c.xun}旬　空亡 {c.xunkong}　貴人 {c.shensha['貴人']}")
    if c.question:
        lines.append(f"占問：{c.question}")
    for ln in lines:
        _center(d, (W // 2, y), ln, F(S(24)), MUTED)
        y += S(36)

    # ---- 天地盤
    top = y + S(16)
    cell = S(150)
    left = (W - cell * 4) // 2
    gan_up = c.sike[0].upper
    zhi_up = c.sike[2].upper
    for e, (cx, cy) in RING.items():
        x0, y0 = left + cx * cell, top + cy * cell
        t = c.tianpan[e]
        hl = t in c.sanchuan
        d.rectangle([x0, y0, x0 + cell, y0 + cell], fill=(255, 252, 245) if not hl else (252, 240, 220), outline=LINE, width=2)
        jiang = c.jiang_of_tian[t]
        _center(d, (x0 + cell // 2, y0 + S(28)), jiang, F(S(22), True), GOLD if jiang == "貴人" else MUTED)
        _center(d, (x0 + cell // 2, y0 + S(76)), t, F(S(52), True), RED if hl else WX_COLOR[wx(t)])
        _center(d, (x0 + cell // 2, y0 + cell - S(24)), f"地 {e}", F(S(18)), MUTED)
        if t in c.xunkong:
            _center(d, (x0 + cell - S(20), y0 + S(20)), "空", F(S(16)), RED)
        if e == c.hour_zhi:
            _center(d, (x0 + S(22), y0 + S(20)), "時", F(S(16), True), RED)
    # 中宮
    cx0, cy0 = left + cell, top + cell
    d.rectangle([cx0, cy0, cx0 + 2 * cell, cy0 + 2 * cell], fill=PANEL, outline=LINE, width=2)
    _center(d, (cx0 + cell, cy0 + S(70)), c.method, F(S(30), True), INK)
    name = c.ke_name
    if len(name) > 9:
        _center(d, (cx0 + cell, cy0 + S(130)), name[:9], F(S(24)), RED)
        _center(d, (cx0 + cell, cy0 + S(164)), name[9:], F(S(24)), RED)
    else:
        _center(d, (cx0 + cell, cy0 + S(135)), name, F(S(26)), RED)
    _center(d, (cx0 + cell, cy0 + S(232)), "天盤加地盤・南上北下", F(S(16)), MUTED)

    # ---- 四課 + 三傳
    y = top + 4 * cell + S(40)
    _center(d, (W // 4, y), "四　課", F(S(28), True), INK)
    _center(d, (W * 3 // 4, y), "三　傳", F(S(28), True), INK)
    y += S(40)
    # 四課：自右至左一二三四
    colw = S(100)
    sx = W // 4 + colw * 3 // 2
    labels = ["一", "二", "三", "四"]
    for i, k in enumerate(c.sike):
        x = sx - i * colw
        _center(d, (x, y + S(10)), k.general, F(S(20)), GOLD if k.general == "貴人" else MUTED)
        _center(d, (x, y + S(58)), k.upper, F(S(44), True), WX_COLOR[wx(k.upper)])
        _center(d, (x, y + S(118)), k.lower, F(S(44), True), WX_COLOR[wx(k.lower)])
        rel = {"下賊上": "賊", "上剋下": "剋", "無剋": "　"}[k.relation]
        _center(d, (x, y + S(166)), f"{labels[i]}課{('・' + rel) if rel.strip() else ''}", F(S(18)), RED if rel.strip() else MUTED)
    # 三傳
    rx = W * 3 // 4
    for j, (lab, z) in enumerate(zip(["初", "中", "末"], c.sanchuan)):
        yy = y + S(20) + j * S(62)
        dg = c.dungan(z) or "〇"
        kong = "空" if z in c.xunkong else ""
        _center(d, (rx - S(150), yy), lab, F(S(20)), MUTED)
        _center(d, (rx - S(100), yy), liuqin(c.gan, z), F(S(22)), INK)
        _center(d, (rx - S(40), yy), dg, F(S(26)), MUTED)
        _center(d, (rx + S(10), yy), z, F(S(40), True), WX_COLOR[wx(z)])
        _center(d, (rx + S(80), yy), c.jiang_of_tian[z], F(S(22)), GOLD if c.jiang_of_tian[z] == "貴人" else INK)
        if kong:
            _center(d, (rx + S(140), yy), kong, F(S(18)), RED)

    # ---- 格局、神煞、年命
    y += S(210)
    d.line([S(60), y, W - S(60), y], fill=LINE, width=2)
    y += S(24)

    def wrap(text, font, maxw):
        out, cur = [], ""
        for ch in text:
            if d.textlength(cur + ch, font=font) > maxw:
                out.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            out.append(cur)
        return out

    f = F(S(21))
    blocks = []
    if c.patterns:
        blocks.append(("格局", "；".join(c.patterns)))
    blocks.append(("取傳", c.method_note))
    blocks.append(("神煞", "　".join(f"{k}{v}" for k, v in c.shensha.items() if k != "貴人")))
    if c.nianming:
        blocks.append(("年命", "　".join(f"{k}{v}" for k, v in c.nianming.items())))
    for title, text in blocks:
        d.text((S(60), y), title, font=F(S(21), True), fill=RED)
        for ln in wrap(text, f, W - S(170)):
            d.text((S(120), y), ln, font=f, fill=INK)
            y += S(32)
        y += S(6)

    img = img.crop((0, 0, W, min(H, y + S(30))))
    img.save(path)
    return path
