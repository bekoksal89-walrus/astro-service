from flask import Flask, request, jsonify
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib.chart import Chart
from flatlib import const
from dateutil import parser as dp
from datetime import datetime, timedelta
import math
import traceback
import os

app = Flask(__name__)

# ─── Sabitler ─────────────────────────────────────────────────────────────────

PLANETS = [
    const.SUN, const.MOON, const.MERCURY, const.VENUS,
    const.MARS, const.JUPITER, const.SATURN,
    const.URANUS, const.NEPTUNE, const.PLUTO
]

SLOW_PLANETS = [const.JUPITER, const.SATURN, const.URANUS, const.NEPTUNE, const.PLUTO]
FAST_PLANETS = [const.SUN, const.MOON, const.MERCURY, const.VENUS, const.MARS]

ASPECTS = [
    (0,   'Kavuşum'),
    (60,  'Sektil'),
    (90,  'Kare'),
    (120, 'Üçgen'),
    (150, 'Kınkontil'),
    (180, 'Karşıt'),
]

ASPECT_NATURE = {
    0: 'nötr', 60: 'olumlu', 90: 'olumsuz',
    120: 'olumlu', 150: 'olumsuz', 180: 'olumsuz',
}

SIGN_TR = {
    'Ari': 'Koç',    'Tau': 'Boğa',   'Gem': 'İkizler',
    'Can': 'Yengeç', 'Leo': 'Aslan',  'Vir': 'Başak',
    'Lib': 'Terazi', 'Sco': 'Akrep',  'Sag': 'Yay',
    'Cap': 'Oğlak',  'Aqu': 'Kova',   'Pis': 'Balık',
}

PLANET_TR = {
    const.SUN: 'Güneş', const.MOON: 'Ay', const.MERCURY: 'Merkür',
    const.VENUS: 'Venüs', const.MARS: 'Mars', const.JUPITER: 'Jüpiter',
    const.SATURN: 'Satürn', const.URANUS: 'Uranüs',
    const.NEPTUNE: 'Neptün', const.PLUTO: 'Plüton',
}

HOUSES = [
    const.HOUSE1,  const.HOUSE2,  const.HOUSE3,  const.HOUSE4,
    const.HOUSE5,  const.HOUSE6,  const.HOUSE7,  const.HOUSE8,
    const.HOUSE9,  const.HOUSE10, const.HOUSE11, const.HOUSE12,
]

# ─── Yardımcı Fonksiyonlar ────────────────────────────────────────────────────

def deg_to_dm(decimal_deg):
    decimal_deg = abs(decimal_deg)
    d = int(decimal_deg)
    remainder = (decimal_deg - d) * 60
    m = int(remainder)
    s = int((remainder - m) * 60)
    return f"{d}°{m:02d}'{s:02d}\""

def orb_to_dm(orb_decimal):
    return deg_to_dm(orb_decimal)

def sign_from_lon(lon):
    signs_en = ['Ari','Tau','Gem','Can','Leo','Vir',
                'Lib','Sco','Sag','Cap','Aqu','Pis']
    idx   = int(lon // 30) % 12
    inner = lon % 30
    return {
        'burc':      SIGN_TR.get(signs_en[idx], signs_en[idx]),
        'burc_lon': deg_to_dm(inner),
    }

def planet_house(chart, planet_lon):
    # Chart içindeki evleri bulmak için chart.houses kullanılır
    house_cusps = []
    for i, h_obj in enumerate(chart.houses):
        house_cusps.append({'ev_no': i + 1, 'kusp_lon': h_obj.lon})

    if not house_cusps:
        return {'ev': None, 'ev_kusp_burcu': None, 'ev_kusp_lon': None}

    for i in range(len(house_cusps)):
        cur = house_cusps[i]['kusp_lon']
        nxt = house_cusps[(i + 1) % len(house_cusps)]['kusp_lon']

        if cur <= nxt:
            inside = cur <= planet_lon < nxt
        else:
            inside = planet_lon >= cur or planet_lon < nxt

        if inside:
            ev_no    = house_cusps[i]['ev_no']
            kusp_lon = house_cusps[i]['kusp_lon']
            sign_inf = sign_from_lon(kusp_lon)
            return {
                'ev':           ev_no,
                'ev_kusp_burcu': sign_inf['burc'],
                'ev_kusp_lon':  deg_to_dm(kusp_lon),
            }
    return {'ev': None, 'ev_kusp_burcu': None, 'ev_kusp_lon': None}

def get_asc(chart):
    """Chart'tan ASC (Yükselen) bilgisini çeker."""
    try:
        asc = chart.get(const.ASC)
        lon = asc.lon
        sign_inf = sign_from_lon(lon)
        return {
            'lon_ham':  round(lon, 4),
            'lon_fmt':  deg_to_dm(lon),
            'burc':     sign_inf['burc'],
            'burc_lon': sign_inf['burc_lon'],
        }
    except:
        return None

def get_planet_movement(obj):
    """Gezegenin hareketi: R (Retrograde), S (Stationary) veya D (Direct)."""
    try:
        movement = getattr(obj, 'movement', None) or getattr(obj, 'motion', None)
        if movement is None:
            return None
        movement = str(movement).strip().upper()
        if movement in ('R', 'RETROGRADE'):
            return 'R'
        elif movement in ('S', 'STATIONARY'):
            return 'S'
        return None  # Direct ise None döndür (gereksiz veri olmasın)
    except:
        return None

def extract_planet_details(chart, harita_adi):
    gezegenler = []
    for p in PLANETS:
        try:
            obj       = chart.get(p)
            lon       = obj.lon
            sign_inf  = sign_from_lon(lon)
            house_inf = planet_house(chart, lon)
            movement  = get_planet_movement(obj)
            entry = {
                'gezegen':       PLANET_TR.get(p, p),
                'lon_ham':       round(lon, 4),
                'lon_fmt':       deg_to_dm(lon),
                'burc':          sign_inf['burc'],
                'burc_lon':      sign_inf['burc_lon'],
                'ev':            house_inf['ev'],
                'ev_kusp_burcu': house_inf['ev_kusp_burcu'],
                'ev_kusp_lon':   house_inf['ev_kusp_lon'],
            }
            if movement:
                entry['hareket'] = movement  # Sadece R veya S ise ekle
            gezegenler.append(entry)
        except:
            continue

    # ASC bilgisini ekle
    asc_info = get_asc(chart)
    return {'harita': harita_adi, 'asc': asc_info, 'gezegenler': gezegenler}

def build_chart(date_str, time_str, lat, lon, tz='+03:00'):
    dt    = dp.parse(f'{date_str} {time_str}')
    fdate = Datetime(dt.strftime('%Y/%m/%d'), dt.strftime('%H:%M'), tz)
    pos   = GeoPos(float(lat), float(lon))
    # CRITICAL: Sadece PLANETS gönderilir, evler otomatik hesaplanır
    return Chart(fdate, pos, IDs=PLANETS)

def build_solar_return_chart(ipo_date_str, ipo_time_str, target_year, lat, lon, tz='+03:00'):
    """
    Solar Return haritası: Güneş'in natal pozisyonuna döndüğü an.
    target_year: Hangi yılın solar return'ü hesaplanacak (örn: 2024)
    Yöntem: Natal Güneş lon'una en yakın tarihi o yıl içinde binary search ile bulur.
    """
    natal_chart = build_chart(ipo_date_str, ipo_time_str, lat, lon, tz)
    natal_sun_lon = natal_chart.get(const.SUN).lon

    # O yılın başından itibaren günlük adımlarla Güneş'in natal lon'a yaklaştığı günü bul
    search_start = dp.parse(f'{target_year}-01-01 12:00')
    best_dt   = None
    best_diff = 999

    for day_offset in range(366):
        candidate = search_start + timedelta(days=day_offset)
        fdate = Datetime(candidate.strftime('%Y/%m/%d'), candidate.strftime('%H:%M'), tz)
        pos   = GeoPos(float(lat), float(lon))
        try:
            c = Chart(fdate, pos, IDs=PLANETS)
            sun_lon = c.get(const.SUN).lon
            diff = angle_between(sun_lon, natal_sun_lon)
            if diff < best_diff:
                best_diff = diff
                best_dt   = candidate
        except:
            continue

    if best_dt is None:
        return None

    # Bulunan günde saatlik hassasiyetle daralt
    for hour_offset in range(-12, 13):
        candidate = best_dt + timedelta(hours=hour_offset)
        fdate = Datetime(candidate.strftime('%Y/%m/%d'), candidate.strftime('%H:%M'), tz)
        pos   = GeoPos(float(lat), float(lon))
        try:
            c = Chart(fdate, pos, IDs=PLANETS)
            sun_lon = c.get(const.SUN).lon
            diff = angle_between(sun_lon, natal_sun_lon)
            if diff < best_diff:
                best_diff = diff
                best_dt   = candidate
        except:
            continue

    fdate = Datetime(best_dt.strftime('%Y/%m/%d'), best_dt.strftime('%H:%M'), tz)
    pos   = GeoPos(float(lat), float(lon))
    return Chart(fdate, pos, IDs=PLANETS)

def build_progress_chart(ipo_date_str, ipo_time_str, target_date_str, lat, lon, tz='+03:00'):
    ipo_dt        = dp.parse(f'{ipo_date_str} {ipo_time_str}')
    target_dt     = dp.parse(f'{target_date_str} 10:00')
    years_elapsed = (target_dt - ipo_dt).days / 365.25
    prog_dt       = ipo_dt + timedelta(days=years_elapsed)
    fdate = Datetime(prog_dt.strftime('%Y/%m/%d'), prog_dt.strftime('%H:%M'), tz)
    pos   = GeoPos(float(lat), float(lon))
    # CRITICAL: Sadece PLANETS gönderilir
    return Chart(fdate, pos, IDs=PLANETS)

def angle_between(deg1, deg2):
    diff = abs(deg1 - deg2) % 360
    return min(diff, 360 - diff)

def find_aspects(chart_a, chart_b, orb, label_a='A', label_b='B'):
    found = []
    for p1 in PLANETS:
        for p2 in PLANETS:
            try:
                lon1 = chart_a.get(p1).lon
                lon2 = chart_b.get(p2).lon
                ang  = angle_between(lon1, lon2)
                for target_deg, aspect_name in ASPECTS:
                    if abs(ang - target_deg) <= orb:
                        orb_val = abs(ang - target_deg)
                        found.append({
                            'acidan':      f'{label_a}:{PLANET_TR.get(p1, p1)}',
                            'aciya':       f'{label_b}:{PLANET_TR.get(p2, p2)}',
                            'aci_tipi':    aspect_name,
                            'derece':      target_deg,
                            'orb_decimal': round(orb_val, 4),
                            'orb_fmt':     orb_to_dm(orb_val),
                            'nitelik':     ASPECT_NATURE[target_deg],
                            'lon_a_ham':   round(lon1, 4),
                            'lon_b_ham':   round(lon2, 4),
                            'lon_a_fmt':   deg_to_dm(lon1),
                            'lon_b_fmt':   deg_to_dm(lon2),
                        })
                        break
            except:
                continue
    found.sort(key=lambda x: x['orb_decimal'])
    return found

def find_transit_progress_aspects(transit_chart, progress_chart, orb_sun_moon=15, orb_other=8):
    found = []
    for slow_p in SLOW_PLANETS:
        for fast_p in FAST_PLANETS:
            try:
                lon_slow = transit_chart.get(slow_p).lon
                lon_fast = progress_chart.get(fast_p).lon
                ang      = angle_between(lon_slow, lon_fast)
                orb      = orb_sun_moon if fast_p in [const.SUN, const.MOON] else orb_other
                for target_deg, aspect_name in ASPECTS:
                    if abs(ang - target_deg) <= orb:
                        orb_val = abs(ang - target_deg)
                        found.append({
                            'acidan':           f'Transit:{PLANET_TR.get(slow_p, slow_p)}',
                            'aciya':            f'Progress:{PLANET_TR.get(fast_p, fast_p)}',
                            'aci_tipi':         aspect_name,
                            'derece':           target_deg,
                            'orb_decimal':      round(orb_val, 4),
                            'orb_fmt':          orb_to_dm(orb_val),
                            'nitelik':          ASPECT_NATURE[target_deg],
                            'uygulanan_orb':    orb,
                            'lon_transit_ham':  round(lon_slow, 4),
                            'lon_progress_ham': round(lon_fast, 4),
                            'lon_transit_fmt':  deg_to_dm(lon_slow),
                            'lon_progress_fmt': deg_to_dm(lon_fast),
                        })
                        break
            except:
                continue
    found.sort(key=lambda x: x['orb_decimal'])
    return found

def score_from_aspects(aspects):
    score = 50
    for a in aspects:
        max_orb = a.get('uygulanan_orb', 8)
        weight  = 1 - (a['orb_decimal'] / (max_orb + 1))
        if a['nitelik'] == 'olumlu':
            score += 8 * weight
        elif a['nitelik'] == 'olumsuz':
            score -= 6 * weight
    return max(0, min(100, round(score, 1)))

def prepare_ai_summary(ticker, natal_d, prog_d, transit_d, solar_d, natal_prog, prog_natal, transit_prog, solar_natal, all_aspects):
    def planet_block(details):
        lines = [f"  {'Gezegen':<10} {'Burç':<10} {'Burç Lon':<14} {'Ev':>3}  {'Kusp Burç':<12} {'Kusp Lon':<14} Hareket", "  " + "-" * 80]
        # ASC satırı
        asc = details.get('asc')
        if asc:
            lines.append(f"  {'ASC':<10} {asc['burc']:<10} {asc['burc_lon']:<14} {'':>3}  {'':12} {'':14}")
        for p in details['gezegenler']:
            ev  = str(p['ev']) if p['ev'] else '?'
            har = p.get('hareket', '')
            lines.append(f"  {p['gezegen']:<10} {p['burc']:<10} {p['burc_lon']:<14} {ev:>3}  {(p['ev_kusp_burcu'] or '?'):<12} {p['ev_kusp_lon'] or '?':<14} {har}")
        return lines

    def aspect_block(aspect_list, limit=10):
        lines = []
        if not aspect_list:
            lines.append("  Aktif açı bulunamadı.")
            return lines
        for a in aspect_list[:limit]:
            lines.append(f"  {a['acidan']:<24} {a['aci_tipi']:<12} {a['aciya']:<24} orb: {a['orb_fmt']:<12} [{a['nitelik']}]")
        return lines

    olumlu  = sum(1 for a in all_aspects if a['nitelik'] == 'olumlu')
    olumsuz = sum(1 for a in all_aspects if a['nitelik'] == 'olumsuz')

    sections = (
        ["=" * 60, f"  {ticker} — Astrolojik Analiz Özeti", "=" * 60, "",
         "── NATAL HARİTA ─────────────────────────────────────────"]
        + planet_block(natal_d)
        + ["", "── PROGRESS HARİTA ──────────────────────────────────────"]
        + planet_block(prog_d)
        + ["", "── TRANSİT HARİTA ───────────────────────────────────────"]
        + planet_block(transit_d)
        + ["", "── SOLAR RETURN HARİTA ──────────────────────────────────"]
        + (planet_block(solar_d) if solar_d else ["  Solar Return hesaplanamadı."])
        + ["", "── NATAL → PROGRESS AÇILARI  (1° orb) ──────────────────"]
        + aspect_block(natal_prog)
        + ["", "── PROGRESS → NATAL SİNASTRİ  (1° orb) ─────────────────"]
        + aspect_block(prog_natal)
        + ["", "── TRANSİT (yavaş) → PROGRESS (hızlı) SİNASTRİ ────────"]
        + aspect_block(transit_prog)
        + ["", "── SOLAR RETURN → NATAL SİNASTRİ  (3° orb) ─────────────"]
        + aspect_block(solar_natal)
        + ["", "── ÖZET ─────────────────────────────────────────────────",
           f"  Toplam aktif açı : {len(all_aspects)}",
           f"  Olumlu           : {olumlu}",
           f"  Olumsuz          : {olumsuz}"]
    )
    return "\n".join(sections)

# ─── Ana Endpoint ─────────────────────────────────────────────────────────────

@app.route('/astro', methods=['POST'])
def calculate():
    try:
        data     = request.json
        ticker   = data.get('ticker', 'UNKNOWN')
        ipo_date = data['ipo_date']
        ipo_time = data.get('ipo_time', '10:00')
        today    = data['today']
        time_now = data.get('time_now', '10:00')
        lat      = data.get('lat', 41.0082)
        lon      = data.get('lon', 28.9784)

        natal    = build_chart(ipo_date, ipo_time, lat, lon)
        progress = build_progress_chart(ipo_date, ipo_time, today, lat, lon)
        transit  = build_chart(today, time_now, lat, lon)

        # Solar Return: bu yılın solar return haritası
        current_year   = dp.parse(today).year
        solar_return   = build_solar_return_chart(ipo_date, ipo_time, current_year, lat, lon)

        natal_details   = extract_planet_details(natal,    'Natal')
        prog_details    = extract_planet_details(progress, 'Progress')
        transit_details = extract_planet_details(transit,  'Transit')
        solar_details   = extract_planet_details(solar_return, 'SolarReturn') if solar_return else None

        natal_to_prog   = find_aspects(natal, progress, orb=1, label_a='Natal', label_b='Progress')
        prog_to_natal   = find_aspects(progress, natal, orb=1, label_a='Progress', label_b='Natal')
        transit_to_prog = find_transit_progress_aspects(transit, progress)
        solar_to_natal  = find_aspects(solar_return, natal, orb=3, label_a='SolarReturn', label_b='Natal') if solar_return else []

        all_aspects = natal_to_prog + prog_to_natal + transit_to_prog + solar_to_natal
        astro_score = score_from_aspects(all_aspects)
        ai_summary  = prepare_ai_summary(
            ticker, natal_details, prog_details, transit_details, solar_details,
            natal_to_prog, prog_to_natal, transit_to_prog, solar_to_natal, all_aspects
        )

        return jsonify({
            'ticker': ticker,
            'astro_score': astro_score,
            'status': 'ok',
            'ai_summary': ai_summary,
            'haritalar': {
                'natal':        natal_details,
                'progress':     prog_details,
                'transit':      transit_details,
                'solar_return': solar_details,
            },
            'acılar': {
                'natal_progress':    natal_to_prog,
                'progress_natal':    prog_to_natal,
                'transit_progress':  transit_to_prog,
                'solar_natal':       solar_to_natal,
            }
        })
    except Exception as e:
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

import os

if __name__ == "__main__":
    # Platformun verdiği PORT'u al, yoksa 8080 kullan
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
