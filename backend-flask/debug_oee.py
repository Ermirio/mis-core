from run import app
from services.watcher import get_current_metrics, get_max_historical, has_recent_capture
import logging

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DebugOEE')

def debug_oee():
    with app.app_context():
        # Hardcode E001 or find active
        eq = 'E001'
        print(f"\n--- Debugging OEE for {eq} ---", flush=True)
        
        curr = get_current_metrics(eq)
        if not curr:
            print("No current metrics found!", flush=True)
            return

        sku = curr.get('last_sku_codigo_field')
        oee = float(curr.get('last_oee_realtime') or 0)
        
        print(f"Current State: SKU={sku}, OEE={oee}", flush=True)
        
        # Check Max Historical for this SKU
        max_oee = get_max_historical(eq, sku, 'oee_atual')
        print(f"Historical Max for SKU {sku}: {max_oee}")
        
        # Check if it would trigger
        if oee > max_oee and oee > 0:
            print(f"✅ CONDITION MET: {oee} > {max_oee}")
        else:
            print(f"❌ CONDITION FAILED: {oee} <= {max_oee}")
            
        # Check Cool down
        recent = has_recent_capture(eq, 'AUTO_OEE', 10)
        print(f"Recent Capture (10m)? {recent}")

        # Check Global Max (to see if user was right about general vs specific)
        from services.diagnostics import client
        try:
            q_global = f"SELECT max(oee_atual) FROM golden_state_profile WHERE equipamento = '{eq}'" 
            rs = client.query(q_global)
            pts = list(rs.get_points())
            max_all = pts[0]['max'] if pts else 0
            print(f"Global Max (All SKUs): {max_all}")
        except:
            pass

if __name__ == '__main__':
    debug_oee()
