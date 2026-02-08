
from models import get_db, MetricsConfig, PredictionData, ControlRecommendation
from sqlalchemy import desc

db = next(get_db())

print('--- CONFIG ---')
conf = db.query(MetricsConfig).first()
if conf:
    print(f'Auto Apply: {conf.auto_apply}')
else:
    print('No MetricsConfig found')

print('\n--- LAST 3 PREDICTIONS ---')
preds = db.query(PredictionData).order_by(desc(PredictionData.timestamp)).limit(3).all()
for p in preds:
    print(f'ID: {p.id}, Measured: {p.measured_value}, Predicted: {p.predicted_value}, Time: {p.timestamp}')

print('\n--- LAST 3 RECOMMENDATIONS ---')
recs = db.query(ControlRecommendation).order_by(desc(ControlRecommendation.timestamp)).limit(3).all()
for r in recs:
    print(f'ID: {r.id}, Rec Val: {r.recommended_value}, Applied: {r.applied}, Time: {r.timestamp}')

db.close()

