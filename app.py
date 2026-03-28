from flask import Flask, request, jsonify
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib.chart import Chart
from flatlib.houses import Houses
from flatlib import const
from dateutil import parser as dp
from datetime import timedelta

app = Flask(__name__)

# Analiz edilecek temel gezegenler
PLANETS = [const.SUN, const.MOON, const.MERCURY, const.VENUS,
           const.MARS, const.JUPITER, const.SATURN]

def get_chart_data(date_str, time_str, lat, lon):
    """Belirlenen zaman ve mekan için Alcabitius ev sistemiyle harita oluşturur."""
    dt = dp.parse(f'{date_str} {time_str}')
    # Türkiye saat dilimi (+03:00) baz alınmıştır.
    fdate = Datetime(dt.strftime('%Y/%m/%d'), dt.strftime('%H:%M'), '+03:00')
    pos = GeoPos(lat, lon)
    chart = Chart(fdate, pos, IDs=PLANETS)
    # Alcabitius ev sistemi ('AL') tanımlanıyor
    houses = Houses(fdate, pos, hsys='AL')
    return chart, houses, fdate, pos

def get_davison_chart(ipo_dt_str, ipo_tm_str, today_str, now_tm_str, lat, lon):
    """İki tarih ve mekanın tam orta noktasını (Davison) hesaplar."""
    d1 = dp.parse(f'{ipo_dt_str} {ipo_tm_str}')
    d2 = dp.parse(f'{today_str} {now_tm_str}')
    
    # Zaman orta noktası
    mid_time = d1 + (d2 - d1) / 2
    
    # Mekan orta noktası (Halka arz yeri ile mevcut yerin ortalaması)
    # Genelde BIST için her iki yer de İstanbul (41.0082, 28.9784) alınabilir.
    return get_chart_data(mid_time.strftime('%Y-%m-%d'), mid_time.strftime('%H:%M'), lat, lon)

def angle_between(deg1, deg2):
    """İki derece arasındaki en kısa mesafeyi (açıyı) hesaplar."""
    diff = abs(deg1 - deg2) % 360
    return min(diff, 360 - diff)

def score_logic(chart1, chart2, rules_type="Standard"):
    """
    Belirlenen kurallara göre puanlama yapar. 
    İster Natal-Transit, ister Davison haritası için kullanılabilir.
    """
    score = 50
    details = []
    orb = 8 # Tolerans payı
    
    # Olumlu Açılar (Örnek Kurallar - Google Doc'una göre güncelleyebilirsin)
    favorable = [(const.JUPITER, const.VENUS, 120, +15), (const.JUPITER, const.SUN, 120, +12)]
    # Olumsuz Açılar
    unfavorable = [(const.SATURN, const.SUN, 90, -12), (const.MARS, const.SATURN, 180, -8)]

    for p1, p2, target, pts in favorable:
        try:
            d1 = chart1.get(p1).lon
            d2 = chart2.get(p2).lon
            if abs(angle_between(d1, d2) - target) <= orb:
                score += pts
                details.append(f"{rules_type} +{pts}: {p1}-{p2} {target}deg")
        except: pass
        
    for p1, p2, target, pts in unfavorable:
        try:
            d1 = chart1.get(p1).lon
            d2 = chart2.get(p2).lon
            if abs(angle_between(d1, d2) - target) <= orb:
                score += pts
                details.append(f"{rules_type} {pts}: {p1}-{p2} {target}deg")
        except: pass
        
    return score, details

@app.route('/astro', methods=['POST'])
def calculate():
    data = request.json
    ticker = data.get('ticker', 'UNKNOWN')
    lat = data.get('lat', 41.0082)
    lon = data.get('lon', 28.9784)

    # 1. Natal ve Transit Haritaları Oluştur
    natal_chart, natal_houses, _, _ = get_chart_data(data['ipo_date'], data.get('ipo_time', '10:00'), lat, lon)
    transit_chart, _, _, _ = get_chart_data(data['today'], data.get('time_now', '10:00'), lat, lon)

    # 2. Davison Haritasını Oluştur
    davison_chart, davison_houses, _, _ = get_davison_chart(data['ipo_date'], data.get('ipo_time', '10:00'), 
                                                           data['today'], data.get('time_now', '10:00'), lat, lon)

    # 3. Puanlamaları Yap
    n_t_score, n_t_details = score_logic(natal_chart, transit_chart, "Natal-Transit")
    dav_score, dav_details = score_logic(davison_chart, davison_chart, "Davison-Internal") # Davison içi açılar

    # Toplam Skoru Sentezle (Örn: %60 Natal-Transit, %40 Davison)
    final_score = (n_t_score * 0.6) + (dav_score * 0.4)
    all_details = n_t_details + dav_details

    return jsonify({
        'ticker': ticker,
        'final_astro_score': round(final_score, 2),
        'details': all_details,
        'house_system': 'Alcabitius',
        'status': 'ok'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
