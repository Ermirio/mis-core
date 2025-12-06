import requests
import sys
import time

def check_url(url, name):
    try:
        print(f"Checking {name} at {url}...", end=" ")
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            print("OK")
            return True
        else:
            print(f"FAILED (Status {resp.status_code})")
            return False
    except Exception as e:
        print(f"FAILED ({e})")
        return False

def main():
    print("=== System Verification ===")
    
    # 1. Check Flask
    flask_ok = check_url("http://localhost:5005/api/health", "Flask Backend")
    
    # 2. Check Django
    django_ok = check_url("http://localhost:8001/api/health/", "Django Backend")
    
    # 3. Check InfluxDB via Flask
    influx_ok = False
    if flask_ok:
        try:
            print("Checking InfluxDB connection via Flask...", end=" ")
            resp = requests.get("http://localhost:5005/api/fabrica/mapa", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and 'oee_fabril_real' in data:
                    print("OK")
                    influx_ok = True
                else:
                    print("FAILED (Invalid response format)")
            else:
                print(f"FAILED (Status {resp.status_code})")
        except Exception as e:
            print(f"FAILED ({e})")

    # 4. Check MySQL via Django
    mysql_ok = False
    if django_ok:
        try:
            print("Checking MySQL connection via Django...", end=" ")
            resp = requests.get("http://localhost:8001/api/linhas/", timeout=5)
            if resp.status_code == 200:
                print("OK")
                mysql_ok = True
            else:
                print(f"FAILED (Status {resp.status_code})")
        except Exception as e:
            print(f"FAILED ({e})")

    print("\n=== Summary ===")
    print(f"Flask Backend: {'✅' if flask_ok else '❌'}")
    print(f"Django Backend: {'✅' if django_ok else '❌'}")
    print(f"InfluxDB: {'✅' if influx_ok else '❌'}")
    print(f"MySQL: {'✅' if mysql_ok else '❌'}")
    
    if flask_ok and django_ok and influx_ok and mysql_ok:
        print("\nSystem appears to be healthy!")
        sys.exit(0)
    else:
        print("\nSome components are not healthy.")
        sys.exit(1)

if __name__ == "__main__":
    main()
