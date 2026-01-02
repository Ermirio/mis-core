from main import app
print("Dumping URL Map:")
for rule in app.url_map.iter_rules():
    print(f"{rule} -> {rule.endpoint} methods={rule.methods}")
