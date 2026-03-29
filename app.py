Şu servisten 500 hatası alıyorum

Servis "from flask import Flask, request, jsonify
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib.chart import Chart
from flatlib import const
from dateutil import parser as dp
from datetime import datetime, timedelta
import math
import traceback

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


# ─── Format Yardımcıları ──────────────────────────────────────────────────────

def deg_to_dm(decimal_deg):
    """284.7250 → '284°43' 30\"' """
    decimal_deg = abs(decimal_deg)
    d = int(decimal_deg)
    remainder = (decimal_deg - d) * 60
    m = int(remainder)
    s = int((remainder - m) * 60)
    return f"{d}°{m:02d}'{s:02d}\""


def orb_to_dm(orb_decimal):
    """0.7250 → '0°43' 30\"' """
    return deg_to_dm(orb_decimal)


def sign_from_lon(lon):
    """
    Ekliptik boylam → Türkçe burç adı + burç içi derece°dakika saniye
    Örn: 245.73 → {'burc': 'Yay', 'burc_lon': '5°43'48\"'}
    """
    signs_en = ['Ari','Tau','Gem','Can','Leo','Vir',
                'Lib','Sco','Sag','Cap','Aqu','Pis']
    idx   = int(lon // 30) % 12
    inner = lon % 30
    return {
        'burc':     SIGN_TR.get(signs_en[idx], signs_en[idx]),
        'burc_lon': deg_to_dm(inner),
    }


# ─── Ev Tespiti ───────────────────────────────────────────────────────────────

def planet_house(chart, planet_lon):
    """
    Gezegenin hangi evde olduğunu, o evin kusp burcunu ve
    kusp boylamını derece°dakika saniye formatında döner.
    """
    house_cusps = []
    for i, h in enumerate(HOUSES):
        try:
            obj = chart.get(h)
            house_cusps.append({'ev_no': i + 1, 'kusp_lon': obj.lon})
        except Exception:
            continue

    if not house_cusps:
        return {'ev': None, 'ev_kusp_burcu': None, 'ev_kusp_lon': None}

    for i in range(len(house_cusps)):
        cur = house_cusps[i]['kusp_lon']
        nxt = house_cusps[(i + 1) % len(house_cusps)]['kusp_lon']

        if cur <= nxt:
            inside = cur <= planet_lon < nxt
        else:
            # Koç/Balık sınırını geçen ev
            inside = planet_lon >= cur or planet_lon < nxt

        if inside:
            ev_no    = house_cusps[i]['ev_no']
            kusp_lon = house_cusps[i]['kusp_lon']
            sign_inf = sign_from_lon(kusp_lon)
            return {
                'ev':          ev_no,
                'ev_kusp_burcu': sign_inf['burc'],
                'ev_kusp_lon': deg_to_dm(kusp_lon),
            }

    return {'ev': None, 'ev_kusp_burcu': None, 'ev_kusp_lon': None}


# ─── Harita Gezegen Detay Çıkarıcı ───────────────────────────────────────────

def extract_planet_details(chart, harita_adi):
    """
    Haritadaki her gezegen için:
      - Türkçe gezegen adı
      - Ham boylam (decimal)
      - Boylam derece°dakika saniye formatı
      - Burç adı (TR)
      - Burç içi derece°dakika saniye
      - Ev numarası
      - Evi kesen burcun adı
      - Evi kesen kusp boylamı (derece°dakika saniye)
    """
    gezegenler = []
    for p in PLANETS:
        try:
            obj      = chart.get(p)
            lon      = obj.lon
            sign_inf = sign_from_lon(lon)
            house_inf = planet_house(chart, lon)

            gezegenler.append({
                'gezegen':       PLANET_TR.get(p, p),
                'lon_ham':       round(lon, 4),
                'lon_fmt':       deg_to_dm(lon),
                'burc':          sign_inf['burc'],
                'burc_lon':      sign_inf['burc_lon'],
                'ev':            house_inf['ev'],
                'ev_kusp_burcu': house_inf['ev_kusp_burcu'],
                'ev_kusp_lon':   house_inf['ev_kusp_lon'],
            })
        except Exception:
            continue

    return {
        'harita':     harita_adi,
        'gezegenler': gezegenler,
    }


# ─── Chart Oluşturucular ──────────────────────────────────────────────────────

def build_chart(date_str, time_str, lat, lon, tz='+03:00'):
    dt    = dp.parse(f'{date_str} {time_str}')
    fdate = Datetime(dt.strftime('%Y/%m/%d'), dt.strftime('%H:%M'), tz)
    pos   = GeoPos(float(lat), float(lon))
    return Chart(fdate, pos, IDs=PLANETS + HOUSES)


def build_progress_chart(ipo_date_str, ipo_time_str, target_date_str,
                          lat, lon, tz='+03:00'):
    """Secondary Progressions — her gün = bir yıl kuralı."""
    ipo_dt        = dp.parse(f'{ipo_date_str} {ipo_time_str}')
    target_dt     = dp.parse(f'{target_date_str} 10:00')
    years_elapsed = (target_dt - ipo_dt).days / 365.25
    prog_dt       = ipo_dt + timedelta(days=years_elapsed)
    fdate = Datetime(prog_dt.strftime('%Y/%m/%d'), prog_dt.strftime('%H:%M'), tz)
    pos   = GeoPos(float(lat), float(lon))
    return Chart(fdate, pos, IDs=PLANETS + HOUSES)


# ─── Açı Hesaplayıcılar ───────────────────────────────────────────────────────

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
            except Exception:
                continue
    found.sort(key=lambda x: x['orb_decimal'])
    return found


def find_transit_progress_aspects(transit_chart, progress_chart,
                                   orb_sun_moon=15, orb_other=8):
    """Yavaş transit gezegen → Hızlı progress gezegeni sinastri."""
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
            except Exception:
                continue
    found.sort(key=lambda x: x['orb_decimal'])
    return found


# ─── Skor ─────────────────────────────────────────────────────────────────────

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


# ─── AI Özeti ─────────────────────────────────────────────────────────────────

def prepare_ai_summary(ticker,
                        natal_d, prog_d, transit_d,
                        natal_prog, prog_natal, transit_prog,
                        all_aspects):

    def planet_block(details):
        lines = []
        lines.append(
            f"  {'Gezegen':<10} {'Burç':<10} {'Burç Lon':<14} "
            f"{'Ev':>3}  {'Kusp Burç':<12} Kusp Lon"
        )
        lines.append("  " + "-" * 72)
        for p in details['gezegenler']:
            ev = str(p['ev']) if p['ev'] else '?'
            lines.append(
                f"  {p['gezegen']:<10} {p['burc']:<10} {p['burc_lon']:<14} "
                f"{ev:>3}  {(p['ev_kusp_burcu'] or '?'):<12} {p['ev_kusp_lon'] or '?'}"
            )
        return lines

    def aspect_block(aspect_list, limit=10):
        lines = []
        if not aspect_list:
            lines.append("  Aktif açı bulunamadı.")
            return lines
        for a in aspect_list[:limit]:
            lines.append(
                f"  {a['acidan']:<24} {a['aci_tipi']:<12} {a['aciya']:<24} "
                f"orb: {a['orb_fmt']:<12} [{a['nitelik']}]"
            )
        return lines

    olumlu  = sum(1 for a in all_aspects if a['nitelik'] == 'olumlu')
    olumsuz = sum(1 for a in all_aspects if a['nitelik'] == 'olumsuz')

    sections = [
        f"{'=' * 60}",
        f"  {ticker} — Astrolojik Analiz Özeti",
        f"{'=' * 60}",
        "",
        "── NATAL HARİTA ─────────────────────────────────────────",
    ] + planet_block(natal_d) + [
        "",
        "── PROGRESS HARİTA ──────────────────────────────────────",
    ] + planet_block(prog_d) + [
        "",
        "── TRANSİT HARİTA ───────────────────────────────────────",
    ] + planet_block(transit_d) + [
        "",
        "── NATAL → PROGRESS AÇILARI  (1° orb) ──────────────────",
    ] + aspect_block(natal_prog) + [
        "",
        "── PROGRESS → NATAL SİNASTRİ  (1° orb) ─────────────────",
    ] + aspect_block(prog_natal) + [
        "",
        "── TRANSİT (yavaş) → PROGRESS (hızlı) SİNASTRİ ────────",
    ] + aspect_block(transit_prog) + [
        "",
        f"── ÖZET ─────────────────────────────────────────────────",
        f"  Toplam aktif açı : {len(all_aspects)}",
        f"  Olumlu           : {olumlu}",
        f"  Olumsuz          : {olumsuz}",
        f"  Astro Skoru      : (response['astro_score'] alanına bak)",
    ]

    return "\n".join(sections)


# ─── Ana Endpoint ─────────────────────────────────────────────────────────────

@app.route('/astro', methods=['POST'])
def calculate():
    data     = request.json
        ticker   = data.get('ticker', 'UNKNOWN')
        ipo_date = data['ipo_date']
        ipo_time = data.get('ipo_time', '10:00')
        today    = data['today']
        time_now = data.get('time_now', '10:00')
        lat      = data.get('lat', 41.0082)
        lon      = data.get('lon', 28.9784)

        # Haritaları oluştur
        natal    = build_chart(ipo_date, ipo_time, lat, lon)
        progress = build_progress_chart(ipo_date, ipo_time, today, lat, lon)
        transit  = build_chart(today, time_now, lat, lon)

        # Her harita için gezegen detayları
        natal_details   = extract_planet_details(natal,    'Natal')
        prog_details    = extract_planet_details(progress, 'Progress')
        transit_details = extract_planet_details(transit,  'Transit')

        # Açılar
        natal_to_prog   = find_aspects(natal, progress, orb=1,
                                       label_a='Natal', label_b='Progress')
        prog_to_natal   = find_aspects(progress, natal, orb=1,
                                       label_a='Progress', label_b='Natal')
        transit_to_prog = find_transit_progress_aspects(
                              transit, progress, orb_sun_moon=15, orb_other=8)

        all_aspects = natal_to_prog + prog_to_natal + transit_to_prog
        astro_score = score_from_aspects(all_aspects)

        ai_summary = prepare_ai_summary(
            ticker,
            natal_details, prog_details, transit_details,
            natal_to_prog, prog_to_natal, transit_to_prog,
            all_aspects,
        )

        return jsonify({
            'ticker':      ticker,
            'astro_score': astro_score,
            'status':      'ok',
            'ai_summary':  ai_summary,
            'haritalar': {
                'natal':    natal_details,
                'progress': prog_details,
                'transit':  transit_details,
            },
            'acılar': {
                'natal_progress':   natal_to_prog,
                'progress_natal':   prog_to_natal,
                'transit_progress': transit_to_prog,
            },
        })

    except Exception as e:
        return jsonify({
            'error': str(e),
            'trace': traceback.format_exc()
        }), 500


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)"

Hata; "{
  "errorMessage": "The service was not able to process your request",
  "errorDescription": "<!doctype html>\n<html lang=en>\n<title>500 Internal Server Error</title>\n<h1>Internal Server Error</h1>\n<p>The server encountered an internal error and was unable to complete your request. Either the server is overloaded or there is an error in the application.</p>\n",
  "errorDetails": {
    "rawErrorMessage": [
      "500 - \"<!doctype html>\\n<html lang=en>\\n<title>500 Internal Server Error</title>\\n<h1>Internal Server Error</h1>\\n<p>The server encountered an internal error and was unable to complete your request. Either the server is overloaded or there is an error in the application.</p>\\n\""
    ],
    "httpCode": "500"
  },
  "n8nDetails": {
    "nodeName": "Astro api",
    "nodeType": "n8n-nodes-base.httpRequest",
    "nodeVersion": 4.4,
    "itemIndex": 0,
    "time": "29.03.2026 19:44:23",
    "n8nVersion": "2.8.3 (Self Hosted)",
    "binaryDataMode": "filesystem",
    "stackTrace": [
      "NodeApiError: The service was not able to process your request",
      "    at ExecuteContext.execute (/usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-nodes-base@file+packages+nodes-base_@aws-sdk+credential-providers@3.808.0_asn1.js@5_8da18263ca0574b0db58d4fefd8173ce/node_modules/n8n-nodes-base/nodes/HttpRequest/V3/HttpRequestV3.node.ts:864:16)",
      "    at processTicksAndRejections (node:internal/process/task_queues:105:5)",
      "    at WorkflowExecute.executeNode (/usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-core@file+packages+core_@opentelemetry+api@1.9.0_@opentelemetry+exporter-trace-otlp_4dbefa9881a7c57a9e05a20ce4387c10/node_modules/n8n-core/src/execution-engine/workflow-execute.ts:1039:8)",
      "    at WorkflowExecute.runNode (/usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-core@file+packages+core_@opentelemetry+api@1.9.0_@opentelemetry+exporter-trace-otlp_4dbefa9881a7c57a9e05a20ce4387c10/node_modules/n8n-core/src/execution-engine/workflow-execute.ts:1218:11)",
      "    at /usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-core@file+packages+core_@opentelemetry+api@1.9.0_@opentelemetry+exporter-trace-otlp_4dbefa9881a7c57a9e05a20ce4387c10/node_modules/n8n-core/src/execution-engine/workflow-execute.ts:1655:27",
      "    at /usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-core@file+packages+core_@opentelemetry+api@1.9.0_@opentelemetry+exporter-trace-otlp_4dbefa9881a7c57a9e05a20ce4387c10/node_modules/n8n-core/src/execution-engine/workflow-execute.ts:2298:11"
    ]
  }
}"
