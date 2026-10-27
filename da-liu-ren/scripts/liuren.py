#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大六壬起課排盤引擎 (Da Liu Ren chart engine)

功能：月將加時 → 天地盤 → 四課 → 九宗門取三傳 → 十二天將 → 遁干、六親、旬空、神煞 → 課名格局

用法：
  python3 liuren.py                                  # 以現在時間（Asia/Taipei）起課
  python3 liuren.py --date "2026-10-27 13:44"        # 指定時間
  python3 liuren.py --day 甲子 --hour 午 --general 亥  # 直接指定日干支、占時、月將（報時/報數起課）
  python3 liuren.py --date "..." --json              # 輸出 JSON
  python3 liuren.py --date "..." --png chart.png     # 另存排盤圖
  python3 liuren.py --birth-year 1990 --gender 男     # 加上本命、行年
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

GAN_WX = dict(zip(GAN, "木木火火土土金金水水"))
ZHI_WX = dict(zip(ZHI, "水土木木土火火土金金土水"))
WX_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}   # A 剋 B
WX_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}  # A 生 B

# 日干寄宮
JIGONG = dict(zip(GAN, "寅辰巳未巳未申戌亥丑"))
# 月將名
GENERAL_NAME = dict(zip("亥戌酉申未午巳辰卯寅丑子",
                        ["登明", "河魁", "從魁", "傳送", "小吉", "勝光", "太乙", "天罡", "太衝", "功曹", "大吉", "神后"]))
# 中氣 → 月將
QI_TO_GENERAL = {"雨水": "亥", "春分": "戌", "穀雨": "酉", "小滿": "申", "夏至": "未", "大暑": "午",
                 "處暑": "巳", "秋分": "辰", "霜降": "卯", "小雪": "寅", "冬至": "丑", "大寒": "子"}
SIMP_TO_TRAD = {"谷雨": "穀雨", "小满": "小滿", "处暑": "處暑"}

TIANJIANG = ["貴人", "螣蛇", "朱雀", "六合", "勾陳", "青龍", "天空", "白虎", "太常", "玄武", "太陰", "天后"]
TIANJIANG_SHORT = dict(zip(TIANJIANG, "貴蛇雀合勾龍空虎常玄陰后"))
# 貴人：晝、夜（甲戊庚牛羊，乙己鼠猴鄉，丙丁豬雞位，壬癸兔蛇藏，六辛逢馬虎）
GUIREN = {"甲": ("丑", "未"), "戊": ("丑", "未"), "庚": ("丑", "未"),
          "乙": ("子", "申"), "己": ("子", "申"),
          "丙": ("亥", "酉"), "丁": ("亥", "酉"),
          "壬": ("卯", "巳"), "癸": ("卯", "巳"),
          "辛": ("午", "寅")}
# 《六壬大全》古法：甲羊戊庚牛，乙猴己鼠求，丙雞丁豬位，壬兔癸蛇遊，六辛逢虎上（晝）；夜貴對沖相反
GUIREN_DAQUAN = {"甲": ("未", "丑"), "戊": ("丑", "未"), "庚": ("丑", "未"),
                 "乙": ("申", "子"), "己": ("子", "申"),
                 "丙": ("酉", "亥"), "丁": ("亥", "酉"),
                 "壬": ("卯", "巳"), "癸": ("巳", "卯"),
                 "辛": ("寅", "午")}
GUIREN_SCHEMES = {"tongxing": GUIREN, "daquan": GUIREN_DAQUAN}
DAY_HOURS = set("卯辰巳午未申")       # 晝貴
SHUN_POS = set("亥子丑寅卯辰")        # 貴人臨此地盤則順佈

XING = dict(zip("子卯寅巳申丑戌未辰午酉亥", "卯子巳申寅戌未丑辰午酉亥"))
SELF_XING = set("辰午酉亥")
GAN_HE = dict(zip(GAN, "己庚辛壬癸甲乙丙丁戊"))
SANHE = [("申", "子", "辰"), ("亥", "卯", "未"), ("寅", "午", "戌"), ("巳", "酉", "丑")]
SANHE_NAME = {frozenset("寅午戌"): "炎上", frozenset("申子辰"): "潤下",
              frozenset("亥卯未"): "曲直", frozenset("巳酉丑"): "從革"}
YIMA = {**{z: "寅" for z in "申子辰"}, **{z: "申" for z in "寅午戌"},
        **{z: "亥" for z in "巳酉丑"}, **{z: "巳" for z in "亥卯未"}}
TAOHUA = {**{z: "酉" for z in "申子辰"}, **{z: "卯" for z in "寅午戌"},
          **{z: "午" for z in "巳酉丑"}, **{z: "子" for z in "亥卯未"}}
HUAGAI = {**{z: "辰" for z in "申子辰"}, **{z: "戌" for z in "寅午戌"},
          **{z: "丑" for z in "巳酉丑"}, **{z: "未" for z in "亥卯未"}}
LU = dict(zip(GAN, "寅卯巳午巳午申酉亥子"))
MENG, ZHONG, JI = set("寅申巳亥"), set("子午卯酉"), set("辰戌丑未")
# 月令旺衰：月支所屬季節之「旺」五行
SEASON_WX = {**{z: "木" for z in "寅卯"}, **{z: "火" for z in "巳午"}, **{z: "金" for z in "申酉"},
             **{z: "水" for z in "亥子"}, **{z: "土" for z in "辰戌丑未"}}


def wangshuai(month_zhi: str, z: str) -> str:
    """旺相休囚死：當令者旺，令生者相，生令者休，剋令者囚，令剋者死"""
    ling, me = SEASON_WX[month_zhi], wx(z)
    if me == ling:
        return "旺"
    if WX_SHENG[ling] == me:
        return "相"
    if WX_SHENG[me] == ling:
        return "休"
    if WX_KE[me] == ling:
        return "囚"
    return "死"


def zi(i: int) -> str:
    return ZHI[i % 12]


def zidx(z: str) -> int:
    return ZHI.index(z)


def wx(c: str) -> str:
    return GAN_WX[c] if c in GAN else ZHI_WX[c]


def yang(c: str) -> bool:
    return (GAN.index(c) if c in GAN else ZHI.index(c)) % 2 == 0


def ke(a: str, b: str) -> bool:
    """a 剋 b"""
    return WX_KE[wx(a)] == wx(b)


def chong(z: str) -> str:
    return zi(zidx(z) + 6)


def liuqin(day_gan: str, z: str) -> str:
    me, other = wx(day_gan), wx(z)
    if me == other:
        return "兄弟"
    if WX_SHENG[other] == me:
        return "父母"
    if WX_SHENG[me] == other:
        return "子孫"
    if WX_KE[me] == other:
        return "妻財"
    return "官鬼"


def ganzhi_index(gz: str) -> int:
    g, z = GAN.index(gz[0]), ZHI.index(gz[1])
    for i in range(60):
        if i % 10 == g and i % 12 == z:
            return i
    raise ValueError(f"不合法的干支：{gz}")


# ---------------------------------------------------------------- 曆法
def calendar_info(dt: datetime, zi_rollover: bool = True) -> dict:
    """由公曆時間取得年月日時干支、月將。dt 視為當地時間（naive）。"""
    from lunar_python import Solar
    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    lunar = solar.getLunar()
    day_gz = lunar.getDayInGanZhiExact() if zi_rollover else lunar.getDayInGanZhi()
    # 月將：取占時之前最近的中氣
    table = dict(lunar.getJieQiTable())
    prev = Solar.fromYmdHms(dt.year, dt.month, dt.day, 12, 0, 0).next(-60).getLunar().getJieQiTable()
    items = list(table.items()) + list(prev.items())
    best_name, best_time = None, None
    for name, sol in items:
        name = SIMP_TO_TRAD.get(name, name)
        if name not in QI_TO_GENERAL:
            continue
        t = datetime(sol.getYear(), sol.getMonth(), sol.getDay(), sol.getHour(), sol.getMinute(), sol.getSecond())
        if t <= dt and (best_time is None or t > best_time):
            best_name, best_time = name, t
    if best_name is None:
        raise RuntimeError("找不到中氣，無法定月將")
    return {
        "solar": dt.strftime("%Y-%m-%d %H:%M"),
        "lunar": f"{lunar.getYearInChinese()}年{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
        "year_gz": lunar.getYearInGanZhiByLiChun(),
        "month_gz": lunar.getMonthInGanZhiExact(),
        "day_gz": day_gz,
        "hour_gz": lunar.getTimeInGanZhi(),
        "hour_zhi": lunar.getTimeZhi(),
        "zhongqi": best_name,
        "zhongqi_time": best_time.strftime("%Y-%m-%d %H:%M"),
        "general": QI_TO_GENERAL[best_name],
    }


# ---------------------------------------------------------------- 資料結構
@dataclass
class Ke:
    idx: int          # 1..4
    upper: str        # 上神
    lower: str        # 下（第一課為日干）
    lower_zhi: str    # 下所在地盤支（第一課為寄宮）
    relation: str     # 下賊上 / 上剋下 / 無剋
    general: str = ""

    def label(self) -> str:
        return f"{self.upper}/{self.lower}"


@dataclass
class Chart:
    day_gz: str
    hour_zhi: str
    general: str
    calendar: dict = field(default_factory=dict)
    question: str = ""
    birth_year: int | None = None
    gender: str | None = None
    # 計算結果
    tianpan: dict = field(default_factory=dict)      # 地盤支 → 天盤支
    jiang_of_tian: dict = field(default_factory=dict)  # 天盤支 → 天將
    sike: list = field(default_factory=list)
    sanchuan: list = field(default_factory=list)
    method: str = ""        # 九宗門
    ke_name: str = ""       # 課名
    method_note: str = ""
    guiren: str = ""
    guiren_daynight: str = ""
    guiren_direction: str = ""
    xun: str = ""
    xunkong: str = ""
    patterns: list = field(default_factory=list)
    shensha: dict = field(default_factory=dict)
    nianming: dict = field(default_factory=dict)

    # ------------- helpers
    @property
    def gan(self) -> str:
        return self.day_gz[0]

    @property
    def zhi(self) -> str:
        return self.day_gz[1]

    def up(self, z: str) -> str:
        """地盤 z 上之天盤神"""
        return self.tianpan[z]

    def below(self, t: str) -> str:
        """天盤 t 所臨之地盤"""
        for e, s in self.tianpan.items():
            if s == t:
                return e
        raise KeyError(t)

    def ws(self, z: str) -> str:
        m = self.calendar.get("month_gz")
        return wangshuai(m[1], z) if m else ""

    def dungan(self, z: str) -> str:
        start = ganzhi_index(self.day_gz) // 10 * 10   # 旬首
        start_zhi = start % 12
        off = (zidx(z) - start_zhi) % 12
        return GAN[off] if off < 10 else ""


# ---------------------------------------------------------------- 起課
def build_chart(day_gz: str, hour_zhi: str, general: str, calendar: dict | None = None,
                question: str = "", birth_year: int | None = None, gender: str | None = None,
                shehai_mode: str = "classic", guiren_scheme: str = "tongxing",
                daynight: str | None = None) -> Chart:
    if len(day_gz) != 2 or day_gz[0] not in GAN or day_gz[1] not in ZHI:
        raise ValueError(f"日干支格式錯誤：{day_gz}")
    ganzhi_index(day_gz)
    if hour_zhi not in ZHI or general not in ZHI:
        raise ValueError("占時、月將須為地支")
    c = Chart(day_gz=day_gz, hour_zhi=hour_zhi, general=general, calendar=calendar or {},
              question=question, birth_year=birth_year, gender=gender)

    # 天地盤：月將加占時
    shift = zidx(general) - zidx(hour_zhi)
    c.tianpan = {zi(i): zi(i + shift) for i in range(12)}

    # 四課
    g, z = c.gan, c.zhi
    jg = JIGONG[g]
    u1 = c.up(jg)
    u2 = c.up(u1)
    u3 = c.up(z)
    u4 = c.up(u3)
    raw = [(1, u1, g, jg), (2, u2, u1, u1), (3, u3, z, z), (4, u4, u3, u3)]
    for idx, upper, lower, lz in raw:
        if ke(lower, upper):
            rel = "下賊上"
        elif ke(upper, lower):
            rel = "上剋下"
        else:
            rel = "無剋"
        c.sike.append(Ke(idx, upper, lower, lz, rel))

    # 旬、空
    start = ganzhi_index(day_gz) // 10 * 10
    c.xun = GAN[0] + ZHI[start % 12]
    c.xunkong = zi(start % 12 + 10) + zi(start % 12 + 11)

    _sanchuan(c, shehai_mode)
    _tianjiang(c, guiren_scheme, daynight)
    _extras(c)
    return c


def _dedupe_by_upper(kes):
    seen, out = set(), []
    for k in kes:
        if k.upper not in seen:
            seen.add(k.upper)
            out.append(k)
    return out


def _shehai_depth(c: Chart, k: Ke, mode: str) -> int:
    """涉害深淺：自上神所臨地盤起，順數至上神本家為止（不含本家），計地盤支與寄宮天干之剋數。
    classic：下賊上 → 數剋上神者；上剋下 → 數上神所剋者。
    shouke：一律數剋上神者（受剋）。"""
    x = k.upper
    start = zidx(k.lower_zhi)
    steps = (zidx(x) - start) % 12
    count_attacker = (k.relation == "下賊上") or mode == "shouke"
    total = 0
    for i in range(steps):
        pos = zi(start + i)
        items = [pos] + [gg for gg, jz in JIGONG.items() if jz == pos]
        for it in items:
            if count_attacker and ke(it, x):
                total += 1
            elif not count_attacker and ke(x, it):
                total += 1
    return total


def _pick_with_biyong(c: Chart, cands, mode: str):
    """多課有剋：比用 → 涉害 → 見機 → 察微 → 綴瑕。回傳 (初傳, 方法, 課名, 說明)"""
    day_yang = yang(c.gan)
    bi = [k for k in cands if yang(k.upper) == day_yang]
    if len(bi) == 1:
        return bi[0].upper, "比用", "知一", f"多課有剋，取與日干陰陽相比者 {bi[0].upper}"
    pool = bi if bi else cands
    depths = {k.upper: _shehai_depth(c, k, mode) for k in pool}
    note = "涉害深淺：" + "、".join(f"{u}={d}" for u, d in depths.items())
    mx = max(depths.values())
    top = [k for k in pool if depths[k.upper] == mx]
    if len(top) == 1:
        return top[0].upper, "涉害", "涉害", note + f"，取最深者 {top[0].upper}"
    meng = [k for k in top if k.lower_zhi in MENG]
    if len(meng) == 1:
        return meng[0].upper, "涉害", "見機", note + f"，深淺相等，取臨孟地者 {meng[0].upper}"
    zhong = [k for k in top if k.lower_zhi in ZHONG]
    if not meng and len(zhong) == 1:
        return zhong[0].upper, "涉害", "察微", note + f"，深淺相等，取臨仲地者 {zhong[0].upper}"
    pick = c.sike[0].upper if day_yang else c.sike[2].upper
    return pick, "涉害", "綴瑕（復等）", note + f"，俱等，{'陽日取干上' if day_yang else '陰日取支上'} {pick}"


def _chain(c: Chart, first: str):
    mid = c.up(first)
    return [first, mid, c.up(mid)]


def _zeike(c: Chart, mode: str):
    """賊剋法（含比用、涉害），無剋回傳 None"""
    zei = _dedupe_by_upper([k for k in c.sike if k.relation == "下賊上"])
    kek = _dedupe_by_upper([k for k in c.sike if k.relation == "上剋下"])
    cands = zei or kek
    if not cands:
        return None
    kind = "下賊上" if zei else "上剋下"
    if len(cands) == 1:
        name = "重審" if zei else "元首"
        return cands[0].upper, "賊剋", name, f"一課{kind}，取 {cands[0].upper} 為用"
    first, method, name, note = _pick_with_biyong(c, cands, mode)
    return first, method, name, f"多課{kind}；" + note


def _sanchuan(c: Chart, mode: str):
    g, z = c.gan, c.zhi
    day_yang = yang(g)
    gan_up, zhi_up = c.sike[0].upper, c.sike[2].upper
    shift = (zidx(c.general) - zidx(c.hour_zhi)) % 12

    # ---------- 伏吟
    if shift == 0:
        r = _zeike(c, mode)
        if r:
            first, src = r[0], ("gan" if r[0] == gan_up else "zhi")
            name, note = "伏吟（不虞）", "伏吟有剋，以剋為用：" + r[3]
        else:
            first, src = (gan_up, "gan") if day_yang else (zhi_up, "zhi")
            name = "伏吟（自任）" if day_yang else "伏吟（自信）"
            note = "伏吟無剋，" + ("陽日取干上神" if day_yang else "陰日取支上神")
        if first in SELF_XING:
            mid = zhi_up if src == "gan" else gan_up
            note += f"；初傳 {first} 自刑，中傳取{'支' if src == 'gan' else '干'}上神"
            if mid == first:
                mid = chong(first)
                note += "（同初傳，改取其沖）"
            name += "・杜傳"
        else:
            mid = XING[first]
        if mid in SELF_XING or XING[mid] == first or XING[mid] == mid:
            last = chong(mid)
            note += f"；中傳 {mid} {'自刑' if mid in SELF_XING else '刑回初傳'}，末傳取沖 {last}"
        else:
            last = XING[mid]
        c.method, c.ke_name, c.method_note = "伏吟", name, note
        c.sanchuan = [first, mid, last]
        return

    # ---------- 返吟
    if shift == 6:
        r = _zeike(c, mode)
        if r:
            c.method, c.ke_name, c.method_note = "返吟", "返吟（無依）", "返吟有剋，依賊剋法：" + r[3]
            c.sanchuan = _chain(c, r[0])
        else:
            ma = YIMA[z]
            c.method, c.ke_name = "返吟", "返吟（無親・井欄射）"
            c.method_note = f"返吟無剋，初傳取日支驛馬 {ma}，中傳支上神，末傳干上神"
            c.sanchuan = [ma, zhi_up, gan_up]
        return

    # ---------- 賊剋 / 比用 / 涉害
    r = _zeike(c, mode)
    if r:
        first, c.method, c.ke_name, c.method_note = r
        c.sanchuan = _chain(c, first)
        return

    distinct = len({(k.upper, k.lower_zhi) for k in c.sike})
    bazhuan_day = JIGONG[g] == z

    # ---------- 八專（干支同位，無剋）
    if bazhuan_day:
        if day_yang:
            first = zi(zidx(gan_up) + 2)
            note = f"八專無剋，陽日自干上神 {gan_up} 順數三位得 {first}"
        else:
            first = zi(zidx(c.sike[3].upper) - 2)
            note = f"八專無剋，陰日自第四課上神 {c.sike[3].upper} 逆數三位得 {first}"
        c.method, c.ke_name, c.method_note = "八專", "八專（帷薄不修）", note + "，中末皆用干上神"
        c.sanchuan = [first, gan_up, gan_up]
        return

    # ---------- 遙剋
    ups = _dedupe_by_upper(c.sike[1:])
    shen_ke_ri = [k for k in ups if ke(k.upper, g)]
    ri_ke_shen = [k for k in ups if ke(g, k.upper)]
    yao = shen_ke_ri or ri_ke_shen
    if yao:
        name = "蒿矢" if shen_ke_ri else "彈射"
        desc = "課神遙剋日干" if shen_ke_ri else "日干遙剋課神"
        if len(yao) == 1:
            first, note = yao[0].upper, f"四課無剋，{desc}，取 {yao[0].upper}"
        else:
            first, _, _, sub = _pick_with_biyong(c, yao, mode)
            note = f"四課無剋，{desc}者多；{sub}"
        c.method, c.ke_name, c.method_note = "遙剋", f"遙剋（{name}）", note
        c.sanchuan = _chain(c, first)
        return

    # ---------- 別責（四課不全）
    if distinct < 4:
        if day_yang:
            hg = GAN_HE[g]
            first = c.up(JIGONG[hg])
            note = f"四課不備、無剋無遙，陽日取干合 {hg}（寄{JIGONG[hg]}）上神 {first}"
        else:
            trio = next(t for t in SANHE if z in t)
            first = trio[(trio.index(z) + 1) % 3]
            note = f"四課不備、無剋無遙，陰日取支三合前一位 {first}"
        c.method, c.ke_name, c.method_note = "別責", "別責（蕪淫）", note + "，中末皆用干上神"
        c.sanchuan = [first, gan_up, gan_up]
        return

    # ---------- 昴星
    if day_yang:
        first = c.up("酉")
        c.sanchuan = [first, zhi_up, gan_up]
        c.ke_name = "昴星（虎視轉蓬）"
        c.method_note = f"四課全、無剋無遙，陽日取地盤酉上神 {first}，中傳支上、末傳干上"
    else:
        first = c.below("酉")
        c.sanchuan = [first, gan_up, zhi_up]
        c.ke_name = "昴星（冬蛇掩目）"
        c.method_note = f"四課全、無剋無遙，陰日取天盤酉所臨地盤 {first}，中傳干上、末傳支上"
    c.method = "昴星"


def _tianjiang(c: Chart, scheme: str = "tongxing", daynight: str | None = None):
    day, night = GUIREN_SCHEMES[scheme][c.gan]
    is_day = (daynight == "晝") if daynight else (c.hour_zhi in DAY_HOURS)
    c.guiren = day if is_day else night
    c.guiren_daynight = "晝貴" if is_day else "夜貴"
    pos = c.below(c.guiren)
    forward = pos in SHUN_POS
    c.guiren_direction = "順" if forward else "逆"
    for i, name in enumerate(TIANJIANG):
        t = zi(zidx(c.guiren) + (i if forward else -i))
        c.jiang_of_tian[t] = name
    for k in c.sike:
        k.general = c.jiang_of_tian[k.upper]


def _extras(c: Chart):
    g, z = c.gan, c.zhi
    sc = c.sanchuan
    pats = []
    s = set(sc)
    if len(s) == 3 and frozenset(s) in SANHE_NAME:
        pats.append(f"三合{SANHE_NAME[frozenset(s)]}")
    if all(x in JI for x in sc):
        pats.append("稼穡（三傳皆土）")
    d1, d2 = (zidx(sc[1]) - zidx(sc[0])) % 12, (zidx(sc[2]) - zidx(sc[1])) % 12
    if d1 == d2 == 1:
        pats.append("進茹（連珠順行）")
    elif d1 == d2 == 11:
        pats.append("退茹（連珠逆行）")
    elif d1 == d2 == 2:
        pats.append("間傳（順間）")
    elif d1 == d2 == 10:
        pats.append("間傳（逆間）")
    w = [wx(x) for x in sc]
    if WX_SHENG[w[0]] == w[1] and WX_SHENG[w[1]] == w[2]:
        pats.append("三傳遞生（初生中、中生末）")
    if WX_SHENG[w[2]] == w[1] and WX_SHENG[w[1]] == w[0]:
        pats.append("三傳遞生入初（末生中、中生初）")
    if WX_KE[w[0]] == w[1] and WX_KE[w[1]] == w[2]:
        pats.append("三傳遞剋")
    kong = [x for x in sc if x in c.xunkong]
    if kong:
        pats.append(f"三傳見空：{'、'.join(kong)}")
    lq = [liuqin(g, x) for x in sc]
    if lq[0] == "妻財" and lq[2] == "官鬼":
        pats.append("傳財化鬼")
    if lq[0] == "官鬼" and lq[2] == "父母":
        pats.append("鬼化為印（官鬼生父母）")
    if "官鬼" not in lq and "子孫" in lq:
        pats.append("三傳有子孫無官鬼")
    gan_up = c.sike[0].upper
    zhi_up = c.sike[2].upper
    if ke(gan_up, g):
        pats.append(f"干上神 {gan_up} 剋日（{c.jiang_of_tian[gan_up]}）")
    if WX_SHENG[wx(gan_up)] == wx(g):
        pats.append(f"干上神 {gan_up} 生日")
    if ke(zhi_up, z):
        pats.append(f"支上神 {zhi_up} 剋支")
    if WX_SHENG[wx(zhi_up)] == wx(z):
        pats.append(f"支上神 {zhi_up} 生支")
    if gan_up in c.xunkong:
        pats.append("干上空亡")
    if zhi_up in c.xunkong:
        pats.append("支上空亡")
    c.patterns = pats

    c.shensha = {
        "旬空": c.xunkong,
        "驛馬": YIMA[z],
        "日祿": LU[g],
        "桃花（咸池）": TAOHUA[z],
        "華蓋": HUAGAI[z],
        "貴人": f"{c.guiren}（{c.guiren_daynight}，{c.guiren_direction}佈）",
    }

    if c.birth_year:
        cur_year = int(c.calendar.get("solar", "2000")[:4]) if c.calendar.get("solar") else None
        ming = zi((c.birth_year - 4) % 12)
        info = {"本命": ming, "本命上神": c.up(ming), "本命上天將": c.jiang_of_tian[c.up(ming)]}
        if cur_year and c.gender in ("男", "女"):
            age = cur_year - c.birth_year + 1
            xn = zi(zidx("寅") + age - 1) if c.gender == "男" else zi(zidx("申") - (age - 1))
            info.update({"虛歲": age, "行年": xn, "行年上神": c.up(xn), "行年上天將": c.jiang_of_tian[c.up(xn)]})
        c.nianming = info


# ---------------------------------------------------------------- 輸出
def chart_to_dict(c: Chart) -> dict:
    g = c.gan

    def node(z):
        return {"支": z, "遁干": c.dungan(z) or "空", "天將": c.jiang_of_tian[z], "六親": liuqin(g, z),
                "五行": wx(z), "旺衰": c.ws(z), "旬空": z in c.xunkong}

    return {
        "曆法": c.calendar,
        "日干支": c.day_gz,
        "占時": c.hour_zhi,
        "月將": f"{c.general}（{GENERAL_NAME[c.general]}）",
        "占問": c.question,
        "旬": f"{c.xun}旬",
        "旬空": c.xunkong,
        "天地盤": [{"地盤": e, "天盤": c.tianpan[e], "天將": c.jiang_of_tian[c.tianpan[e]]} for e in ZHI],
        "四課": [{"課": k.idx, "上神": k.upper, "下": k.lower, "關係": k.relation, "天將": k.general,
                 "上神六親": liuqin(g, k.upper), "上神旺衰": c.ws(k.upper)} for k in c.sike],
        "三傳": dict(zip(["初傳", "中傳", "末傳"], [node(x) for x in c.sanchuan])),
        "九宗門": c.method,
        "課名": c.ke_name,
        "取傳說明": c.method_note,
        "格局": c.patterns,
        "神煞": c.shensha,
        "年命": c.nianming,
    }


def chart_to_text(c: Chart) -> str:
    g = c.gan
    L = []
    cal = c.calendar
    L.append("【大六壬排盤】")
    if cal:
        L.append(f"公曆：{cal['solar']}　農曆：{cal['lunar']}")
        L.append(f"四柱：{cal['year_gz']}年 {cal['month_gz']}月 {c.day_gz}日 {cal['hour_gz']}時")
        L.append(f"月將：{c.general}（{GENERAL_NAME[c.general]}），{cal['zhongqi']}（{cal['zhongqi_time']}）後")
    else:
        L.append(f"日干支：{c.day_gz}　占時：{c.hour_zhi}　月將：{c.general}（{GENERAL_NAME[c.general]}）")
    L.append(f"旬：{c.xun}旬　旬空：{c.xunkong}　貴人：{c.shensha['貴人']}")
    if c.question:
        L.append(f"占問：{c.question}")
    L.append("")
    L.append("【天地盤】（地盤→天盤／天將）")
    row = []
    for e in ZHI:
        t = c.tianpan[e]
        row.append(f"{e}→{t}{TIANJIANG_SHORT[c.jiang_of_tian[t]]}")
    L.append("　".join(row[:6]))
    L.append("　".join(row[6:]))
    L.append("")
    L.append("【四課】（由右至左：一課 二課 三課 四課）")
    ks = list(reversed(c.sike))
    L.append("天將　" + "　".join(f"{k.general}" for k in ks))
    L.append("上神　" + "　　".join(k.upper for k in ks))
    L.append("下神　" + "　　".join(k.lower for k in ks))
    L.append("關係　" + "　".join(k.relation for k in ks))
    if c.calendar.get("month_gz"):
        L.append("旺衰　" + "　　".join(c.ws(k.upper) for k in ks) + f"　（上神，以{c.calendar['month_gz'][1]}月論）")
    L.append("")
    L.append(f"【三傳】{c.method}・{c.ke_name}")
    for lab, x in zip(["初傳", "中傳", "末傳"], c.sanchuan):
        dg = c.dungan(x) or "空"
        mark = "（空）" if x in c.xunkong else ""
        w = f"　{c.ws(x)}" if c.ws(x) else ""
        L.append(f"{lab}：{liuqin(g, x)}　{dg}{x}{mark}　{c.jiang_of_tian[x]}{w}")
    L.append(f"取傳：{c.method_note}")
    L.append("")
    if c.patterns:
        L.append("【格局】" + "；".join(c.patterns))
    L.append("【神煞】" + "　".join(f"{k}:{v}" for k, v in c.shensha.items() if k != "貴人"))
    if c.nianming:
        L.append("【年命】" + "　".join(f"{k}:{v}" for k, v in c.nianming.items()))
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(description="大六壬起課排盤")
    p.add_argument("--date", "-d", help="占問時間 YYYY-MM-DD HH:MM（當地時間，預設現在）")
    p.add_argument("--tz", default="8", help="未給 --date 時的時區偏移小時，預設 8（台北）")
    p.add_argument("--day", help="直接指定日干支，如 甲子（需同時給 --hour 與 --general）")
    p.add_argument("--hour", help="占時地支，如 午（可搭配 --date 覆寫，例如報時起課）")
    p.add_argument("--general", help="月將地支，如 亥（可覆寫自動計算）")
    p.add_argument("--question", "-q", default="", help="占問事項（記錄用）")
    p.add_argument("--birth-year", type=int, help="出生年（取本命）")
    p.add_argument("--gender", choices=["男", "女"], help="性別（取行年）")
    p.add_argument("--no-zi-rollover", action="store_true", help="夜子時（23點後）不換日")
    p.add_argument("--shehai", choices=["classic", "shouke"], default="classic",
                   help="涉害計法：classic=賊數剋上神、剋數上神所剋；shouke=一律數受剋")
    p.add_argument("--guiren", choices=["tongxing", "daquan"], default="tongxing",
                   help="貴人歌訣：tongxing=甲戊庚牛羊（預設）；daquan=《六壬大全》甲羊戊庚牛")
    p.add_argument("--daynight", choices=["晝", "夜"], help="強制晝貴/夜貴（預設卯至申時為晝）")
    p.add_argument("--json", "-j", action="store_true", help="輸出 JSON")
    p.add_argument("--png", help="另存排盤圖 PNG 路徑")
    a = p.parse_args(argv)

    cal = {}
    if a.day:
        if not (a.hour and a.general):
            p.error("--day 需搭配 --hour 與 --general")
        day_gz, hour, gen = a.day, a.hour, a.general
    else:
        if a.date:
            dt = datetime.strptime(a.date.strip().replace("/", "-").replace("T", " "),
                                   "%Y-%m-%d %H:%M" if len(a.date.strip()) > 10 else "%Y-%m-%d")
        else:
            dt = datetime.now(timezone(timedelta(hours=float(a.tz)))).replace(tzinfo=None, second=0, microsecond=0)
        cal = calendar_info(dt, zi_rollover=not a.no_zi_rollover)
        day_gz = cal["day_gz"]
        hour = a.hour or cal["hour_zhi"]
        gen = a.general or cal["general"]

    c = build_chart(day_gz, hour, gen, calendar=cal, question=a.question,
                    birth_year=a.birth_year, gender=a.gender, shehai_mode=a.shehai,
                    guiren_scheme=a.guiren, daynight=a.daynight)
    if a.json:
        print(json.dumps(chart_to_dict(c), ensure_ascii=False, indent=2))
    else:
        print(chart_to_text(c))
    if a.png:
        sys.path.insert(0, __import__("os").path.dirname(__file__))
        from chart import render_png
        render_png(c, a.png)
        print(f"\n排盤圖已存：{a.png}", file=sys.stderr)


if __name__ == "__main__":
    main()
