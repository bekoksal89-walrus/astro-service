from flask import Flask, request, jsonify
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib.chart import Chart
from flatlib import const
from dateutil import parser as dp
import os

app = Flask(__name__)

# Analiz edilecek temel gezegenler
PLANETS = [const.SUN, const.MOON, const.MERCURY, const.VENUS,
           const.MARS, const.JUPITER, const.SATURN]

def get_chart_data(date_str, time_str, lat, lon):
    """
    Belirlenen zaman ve mekan için harita oluşturur.
    Hata payını sıfırlamak için ev sistemi parametresi kaldırılmıştır.
    """
    dt = dp.parse(f'{date_str} {time_str}')
    # Türkiye saat dilimi (+03:00)
    fdate = Datetime(dt.strftime('%Y/%m/%d'), dt.strftime('%H:%M'), '+03:00')
    pos = GeoPos(lat, lon)
    
    # En stabil form: Sadece tarih, konum ve gezegen listesi
    chart = Chart(fdate, pos, IDs=PLANETS)
    return chart

def get_davison_chart(ipo_dt_str, ipo_tm_str, today_str, now_tm_str, lat, lon):
    """İki tarih ve mekanın tam orta noktasını (Davison) hesaplar."""
    try:
        d1 = dp.parse(f'{ipo_dt_str} {ipo_tm_str}')
        d2 = dp.parse(f'{today_str} {now_tm_str}')
        mid_time = d1 + (d2 - d1) / 2
        return get_chart_data(mid_time.strftime('%Y-%m-%d'), mid_time.strftime('%H:%M'), lat, lon)
    except:
        # Hata durumunda bugün için bir harita döner
        return get_chart_data(today_str, now_tm_str, lat, lon)

def angle_between(deg1, deg2):
    """İki derece arasındaki en kısa mesafeyi hesaplar."""
    diff = abs(deg1 - deg2) % 360
    return min(diff, 360 - diff)

def score_logic(chart1, chart2, rules_type="Standard"):
    """Puanlama motoru."""
    score = 50
    details = []
    orb = 8 
    
    favorable = [(const.JUPITER, const.VENUS, 120, +15), (const.JUPITER, const.SUN, 120, +12)]
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
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data provided'}), 400
            
        ticker = data.get('ticker', 'UNKNOWN')
        lat = data.get('lat', 41.0082) 
        lon = data.get('lon', 28.9784)

        # 1. Natal ve Transit Haritaları
        natal_chart = get_chart_data(data['ipo_date'], data.get('ipo_time', '10:00'), lat, lon)
        transit_chart = get_chart_data(data['today'], data.get('time_now', '10:00'), lat, lon)

        # 2. Davison Haritası
        davison_chart = get_davison_chart(data['ipo_date'], data.get('ipo_time', '10:00'), 
                                         data['today'], data.get('time_now', '10:00'), lat, lon)

        # 3. Puanlama
        n_t_score, n_t_details = score_logic(natal_chart, transit_chart, "Natal-Transit")
        dav_score, dav_details = score_logic(davison_chart, davison_chart, "Davison-Internal")

        final_score = (n_t_score * 0.6) + (dav_score * 0.4)
        all_details = n_t_details + dav_details

        return jsonify({
            'ticker': ticker,
            'final_astro_score': round(final_score, 2),
            'details': all_details,
            'status': 'ok'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
