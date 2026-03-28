from flask import Flask, request, jsonify
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib.chart import Chart
from flatlib import const
from dateutil import parser as dp

app = Flask(__name__)

PLANETS = [const.SUN, const.MOON, const.MERCURY, const.VENUS,
           const.MARS, const.JUPITER, const.SATURN]

def get_chart(date_str, time_str, lat, lon):
    dt = dp.parse(f'{date_str} {time_str}')
    fdate = Datetime(dt.strftime('%Y/%m/%d'), dt.strftime('%H:%M'), '+03:00')
    pos = GeoPos(lat, lon)
    return Chart(fdate, pos, IDs=PLANETS)

def angle_between(deg1, deg2):
    diff = abs(deg1 - deg2) % 360
    return min(diff, 360 - diff)

def score_aspects(natal, transit):
    score = 50
    favorable = [(const.JUPITER, const.VENUS, 120, +15),
                 (const.JUPITER, const.SUN,   120, +12),
                 (const.VENUS,   const.SUN,    60, +8),
                 (const.JUPITER, const.MERCURY,120, +10)]
    unfavorable = [(const.SATURN, const.SUN,   90, -12),
                   (const.SATURN, const.MOON,  90, -10),
                   (const.MARS,   const.SATURN,180, -8)]
    orb = 8
    details = []
    for p1, p2, target, pts in favorable:
        try:
            d1 = natal.get(p1).lon
            d2 = transit.get(p2).lon
            ang = angle_between(d1, d2)
            if abs(ang - target) <= orb:
                score += pts
                details.append(f'+{pts}: {p1}-{p2} {target}deg')
        except: pass
    for p1, p2, target, pts in unfavorable:
        try:
            d1 = natal.get(p1).lon
            d2 = transit.get(p2).lon
            ang = angle_between(d1, d2)
            if abs(ang - target) <= orb:
                score += pts
                details.append(f'{pts}: {p1}-{p2} {target}deg')
        except: pass
    return max(0, min(100, score)), details

@app.route('/astro', methods=['POST'])
def calculate():
    data = request.json
    natal  = get_chart(data['ipo_date'], data.get('ipo_time', '10:00'),
                       data.get('lat', 41.0082), data.get('lon', 28.9784))
    transit = get_chart(data['today'], data.get('time_now', '10:00'),
                        data.get('lat', 41.0082), data.get('lon', 28.9784))
    score, details = score_aspects(natal, transit)
    return jsonify({'ticker': data['ticker'], 'astro_score': score,
                    'details': details, 'status': 'ok'})

@app.route('/health')
def health(): return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
