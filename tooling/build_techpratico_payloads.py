"""One-shot: monta os payloads do callback TechPratico para os 22 exames
categoria B selecionados (NÃO envia — só gera os JSON e um manifesto).

Payload por exame: {id_analise (=hash), resultado (A/R/N), relatorio (PDF base64)}
Saída: /tmp/tp_payloads/<hash>.json + manifesto em stdout.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os

ANALYSES_DIR = os.environ.get("VALBOT_ANALYSES_DIR", "/opt/valbot/storage/analyses")
OUT_DIR = "/tmp/tp_payloads"

# (hash == id_analise, resultado VALBOT == presencial nos matches; A p/ aprovados, R p/ reprovado)
EXAMS = [
    ("609b6c3c57b94bef8f3bb5f9347878a9", "A"),
    ("024e83545148409583474da8b4d80ab5", "A"),
    ("17f3801e259046adb3c695b75178b2c6", "A"),
    ("9e0a411d68ad4d87980898a853fe5262", "A"),
    ("d63252cb0e1d4ecdb5e8164a71817699", "A"),
    ("284530f7b8c7434ea77feed9e53af1f7", "A"),
    ("25a4b2d50bd149f7b3a99e55023a6365", "A"),
    ("e58bb645425444c6bf0fc2fbb5f77314", "A"),
    ("b31722d8cb914c889872a3a1a17a81c7", "A"),
    ("3c87d0d169b14b7cbead06bb8b3787cb", "A"),
    ("8413a4707d82454e8f2429f5cdbe79cc", "A"),
    ("1f164cfc1d2d481085a3ce735023e7dc", "A"),
    ("e7223142b26744b2a613e6f543a7ce80", "A"),
    ("3f6c79a0dc184fbc9ebef7c06d71a17b", "A"),
    ("7fa0fbf7b6584bdbbb627523b01adb49", "A"),
    ("b354ac05e65c473aa04cbdc9e872dc74", "A"),
    ("5c5b5b87b8064b8f9d9152a4e5516124", "A"),
    ("dddebbb146f54e3985246566ff7f0428", "A"),
    ("cb836db2807b453cb4398f3d5fc2dff6", "A"),
    ("222e5213a4ef4c9183ce390c64ae6c74", "A"),
    ("38a8a6095ad748fbbeabc379463deccc", "A"),
    ("7c2ba6b7594b4648ab0ce6e5edba3b2f", "R"),
]


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    print("hash                             | res | pdf_bytes | b64_len | pdf_sha256[:12]")
    print("-" * 86)
    total = 0
    for h, resultado in EXAMS:
        pdf_path = os.path.join(ANALYSES_DIR, h, "laudo.pdf")
        raw = open(pdf_path, "rb").read()
        if not raw:
            raise SystemExit(f"PDF vazio: {h}")
        b64 = base64.b64encode(raw).decode("ascii")
        payload = {"id_analise": h, "resultado": resultado, "relatorio": b64}
        with open(os.path.join(OUT_DIR, f"{h}.json"), "w") as f:
            json.dump(payload, f)
        sha = hashlib.sha256(raw).hexdigest()[:12]
        print(f"{h} |  {resultado}  | {len(raw):8d}  | {len(b64):7d} | {sha}")
        total += 1
    print("-" * 86)
    print(f"{total} payloads gerados em {OUT_DIR}/  (NENHUM enviado)")


if __name__ == "__main__":
    main()
