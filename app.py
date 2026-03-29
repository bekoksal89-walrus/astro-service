from flask import Flask, request, jsonify
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib.chart import Chart
from flatlib import const
from dateutil import parser as dp
from datetime import datetime, timedelta

app = Flask(__name__)

# Tüm gezegenler
PLANETS = [
    const.SUN, const.MOON, const.MERCURY, const.VENUS,
    const.MARS, const.JUPITER, const.SATURN,
    const.URANUS, const.NEPTUNE, const.PLUTO
]

# Hızlı / yavaş gezegen ayrımı (transit sinastri orb kuralı için)
SLOW_PLANETS  = [const.SATURN, const.URANUS, const.NEPTUNE, const.PLUTO, const.JUPITER]
FAST_PLANETS  = [const.SUN, const.MOON, const.MERCURY, const.VENUS, const.MARS]

# Desteklenen açılar ve isimleri
ASPECTS = [
    (0,   'Kavuşum'),
    (60,  'Sektil'),
    (90,  'Kare'),
    (120, 'Üçgen'),
    (150, 'Kınkontil'),
    (180, 'Karşıt'),
]

# Açı niteliği
ASPECT_NATURE = {
    0:   'nötr',
    60:  'olumlu',
    90:  'olumsuz',
    120: 'olumlu',
    150: 'olumsuz',
    180: 'olumsuz',
}


# ─── Yardımcı Fonksiyonlar ────────────────────────────────────────────────────

def build_chart(date_str, time_str, lat, lon, tz='+03:00'):
    """Verilen tarih/saat/konum için natal chart döner."""
    dt = dp.parse(f'{date_str} {time_str}')
    fdate = Datetime(dt.strftime('%Y/%m/%d'), dt.strftime('%H:%M'), tz)
    pos = GeoPos(float(lat), float(lon))
    return Chart(fdate, pos, IDs=PLANETS)


def build_progress_chart(ipo_date_str, ipo_time_str, target_date_str, lat, lon, tz='+03:00'):
    """
    Secondary Progressions (ikincil ilerleme):
    Her bir gün = bir yıl kuralıyla hesaplanır.
    ipo_date'den target_date'e kadar geçen yıl sayısı kadar gün ileri gidilir.
    """
    ipo_dt    = dp.parse(f'{ipo_date_str} {ipo_time_str}')
    target_dt = dp.parse(f'{target_date_str} 10:00')

    years_elapsed = (target_dt - ipo_dt).days / 365.25
    progressed_dt = ipo_dt + timedelta(days=years_elapsed)

    prog_date = progressed_dt.strftime('%Y/%m/%d')
    prog_time = progressed_dt.strftime('%H:%M')

    fdate = Datetime(prog_date, prog_time, tz)
    pos   = GeoPos(float(lat), float(lon))
    return Chart(fdate, pos, IDs=PLANETS)


def angle_between(deg1, deg2):
    """İki derece arasındaki en kısa açıyı döner (0-180)."""
    diff = abs(deg1 - deg2) % 360
    return min(diff, 360 - diff)


def find_aspects(chart_a, chart_b, orb, label_a='A', label_b='B'):
    """
    İki harita arasındaki tüm açıları bulur.
    Her gezegen çifti için orb dahilindeki en yakın açıyı raporlar.
    """
    found = []
    for p1 in PLANETS:
        for p2 in PLANETS:
            try:
                lon1 = chart_a.get(p1).lon
                lon2 = chart_b.get(p2).lon
                ang  = angle_between(lon1, lon2)

                for target_deg, aspect_name in ASPECTS:
                    if abs(ang - target_deg) <= orb:
                        exact_diff = round(abs(ang - target_deg), 2)
                        found.append({
                            'acidan':   f'{label_a}:{p1}',
                            'aciya':    f'{label_b}:{p2}',
                            'aci_tipi': aspect_name,
                            'derece':   target_deg,
                            'orb':      exact_diff,
                            'nitelik':  ASPECT_NATURE[target_deg],
                            'lon_a':    round(lon1, 2),
                            'lon_b':    round(lon2, 2),
                        })
                        break  # aynı gezegen çifti için en yakın açıyı al
            except Exception:
                continue
    # Orb'a göre sırala (en exact önce)
    found.sort(key=lambda x: x['orb'])
    return found


def find_transit_progress_aspects(transit_chart, progress_chart, orb_sun_moon=15, orb_other=8):
    """
    Transit sinastri: Yavaş transit gezegen → Hızlı progress gezegeni
    Güneş ve Ay için 15 derece, diğerleri için 8 derece orb.
    """
    found = []
    for slow_p in SLOW_PLANETS:
        for fast_p in FAST_PLANETS:
            try:
                lon_slow = transit_chart.get(slow_p).lon
                lon_fast = progress_chart.get(fast_p).lon
                ang      = angle_between(lon_slow, lon_fast)

                # Güneş ve Ay için farklı orb
                orb = orb_sun_moon if fast_p in [const.SUN, const.MOON] else orb_other

                for target_deg, aspect_name in ASPECTS:
                    if abs(ang - target_deg) <= orb:
                        exact_diff = round(abs(ang - target_deg), 2)
                        found.append({
                            'acidan':        f'Transit:{slow_p}',
                            'aciya':         f'Progress:{fast_p}',
                            'aci_tipi':      aspect_name,
                            'derece':        target_deg,
                            'orb':           exact_diff,
                            'nitelik':       ASPECT_NATURE[target_deg],
                            'uygulanan_orb': orb,
                        })
                        break
            except Exception:
                continue
    found.sort(key=lambda x: x['orb'])
    return found


def score_from_aspects(aspects):
    """
    Açı listesinden 0-100 arası skor üretir.
    Olumlu açılar puan ekler, olumsuzlar düşürür.
    Orb'a yakınlık ağırlık katsayısı olarak kullanılır.
    """
    score = 50
    for a in aspects:
        # Orb ne kadar küçükse etki o kadar güçlü
        max_orb   = a.get('uygulanan_orb', 8)
        weight    = 1 - (a['orb'] / (max_orb + 1))

        if a['nitelik'] == 'olumlu':
            score += 8 * weight
        elif a['nitelik'] == 'olumsuz':
            score -= 6 * weight
        # nötr (kavuşum): bağlama göre — burada nötr bırakıyoruz

    return max(0, min(100, round(score, 1)))


def prepare_ai_summary(ticker, natal_prog, prog_natal, transit_prog, all_aspects_flat):
    """
    Abacus AI / Claude için yapılandırılmış metin özeti hazırlar.
    """
    lines = [
        f"=== {ticker} — Astrolojik Analiz Özeti ===",
        "",
        "[ NATAL → PROGRESS AÇILARI ] (1° orb)",
    ]
    if natal_prog:
        for a in natal_prog[:5]:  # en exact 5 açı
            lines.append(
                f"  {a['acidan']} {a['aci_tipi']} {a['aciya']} "
                f"(orb: {a['orb']}°, {a['nitelik']})"
            )
    else:
        lines.append("  Aktif açı bulunamadı.")

    lines += ["", "[ PROGRESS → NATAL SİNASTRİ ] (1° orb)"]
    if prog_natal:
        for a in prog_natal[:5]:
            lines.append(
                f"  {a['acidan']} {a['aci_tipi']} {a['aciya']} "
                f"(orb: {a['orb']}°, {a['nitelik']})"
            )
    else:
        lines.append("  Aktif açı bulunamadı.")

    lines += ["", "[ TRANSİT (yavaş) → PROGRESS (hızlı) SİNASTRİ ]"]
    if transit_prog:
        for a in transit_prog[:8]:
            lines.append(
                f"  {a['acidan']} {a['aci_tipi']} {a['aciya']} "
                f"(orb: {a['orb']}°, uygulanan orb: {a['uygulanan_orb']}°, {a['nitelik']})"
            )
    else:
        lines.append("  Aktif açı bulunamadı.")

    # Genel değerlendirme
    olumlu   = sum(1 for a in all_aspects_flat if a['nitelik'] == 'olumlu')
    olumsuz  = sum(1 for a in all_aspects_flat if a['nitelik'] == 'olumsuz')
    lines += [
        "",
        f"[ GENEL ] Olumlu açı: {olumlu} | Olumsuz açı: {olumsuz}",
    ]

    return "\n".join(lines)


# ─── Ana Endpoint ─────────────────────────────────────────────────────────────

@app.route('/astro', methods=['POST'])
def calculate():
    data = request.json

    # Zorunlu alanlar
    ticker    = data.get('ticker', 'UNKNOWN')
    ipo_date  = data['ipo_date']
    ipo_time  = data.get('ipo_time', '10:00')
    today     = data['today']
    time_now  = data.get('time_now', '10:00')
    lat       = data.get('lat', 41.0082)
    lon       = data.get('lon', 28.9784)

    # 1. Natal harita (IPO anı)
    natal = build_chart(ipo_date, ipo_time, lat, lon)

    # 2. Progress harita (bugüne göre ilerlemiş natal)
    progress = build_progress_chart(ipo_date, ipo_time, today, lat, lon)

    # 3. Transit harita (bugünkü gökyüzü)
    transit = build_chart(today, time_now, lat, lon)

    # 4. Natal → Progress açıları (1° orb)
    natal_to_prog = find_aspects(natal, progress, orb=1,
                                 label_a='Natal', label_b='Progress')

    # 5. Progress → Natal sinastri (1° orb)
    prog_to_natal = find_aspects(progress, natal, orb=1,
                                 label_a='Progress', label_b='Natal')

    # 6. Transit (yavaş) → Progress (hızlı) sinastri
    transit_to_prog = find_transit_progress_aspects(transit, progress,
                                                    orb_sun_moon=15, orb_other=8)

    # Tüm açıları birleştir (skor için)
    all_aspects = natal_to_prog + prog_to_natal + transit_to_prog

    # Genel astro skoru
    astro_score = score_from_aspects(all_aspects)

    # AI için özet metin
    ai_summary = prepare_ai_summary(
        ticker, natal_to_prog, prog_to_natal, transit_to_prog, all_aspects
    )

    return jsonify({
        'ticker':       ticker,
        'astro_score':  astro_score,
        'status':       'ok',
        'ai_summary':   ai_summary,
        'detaylar': {
            'natal_progress':    natal_to_prog,
            'progress_natal':    prog_to_natal,
            'transit_progress':  transit_to_prog,
        }
    })


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
