
def normalize_line_name(linha_nome):
    if not linha_nome: return linha_nome
    if linha_nome.startswith("L") and len(linha_nome) <= 3 and linha_nome[1:].isdigit():
        return linha_nome
    if "Linha" in linha_nome:
        parts = linha_nome.split()
        if len(parts) > 1 and parts[1].isdigit():
             return f"L{parts[1].zfill(2)}" # Ensure L01, L02
    return linha_nome.replace("Linha ", "L")

print(f"Linha 01 -> {normalize_line_name('Linha 01')}")
print(f"Linha 02 -> {normalize_line_name('Linha 02')}")
print(f"Linha 1 -> {normalize_line_name('Linha 1')}")
print(f"L01 -> {normalize_line_name('L01')}")
