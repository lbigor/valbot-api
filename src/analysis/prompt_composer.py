"""Composer da arquitetura modular v26 — monta o system prompt sob demanda
a partir de fragments por categoria CNH e por câmera.

Layout do diretório:
    tooling/bench_demo/presets/v26/
        discovery/layout_2x2.md        ← FASE 1
        cat_<X>/
            base.md                    ← regras gerais + schema
            cam_frontal.md             ← regras visíveis na FRONTAL
            cam_interna.md             ← regras visíveis na INTERNA
            cam_lateral_direita.md     ← idem
            cam_traseira_esq.md        ← idem

O composer:
  1. Lê `cat_<X>/base.md`
  2. Pra cada quadrante do layout (na ordem TL→TR→BL→BR), injeta um header
     "## QUADRANTE TL = câmera FRONTAL" e o corpo do `cam_<camera>.md`
     correspondente.
  3. Devolve a string final.

Categorias suportadas hoje: B (carro). Cat A/C/D/E ficam pra Phase 3 — o
composer pega a Cat B como default seguro quando outras categorias chegam,
e marca `layout_disagreement` no output pro humano revisar (vide base.md).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.analysis.layout_discovery import CameraMap, QuadrantName

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRESET_V26 = PROJECT_ROOT / "tooling" / "bench_demo" / "presets" / "v26"

# Mapeamento categoria → diretório de fragments. A base de regras MBEDV é
# comum a todas as categorias (a maioria das fichas se aplica a TODAS), então
# todas reusam `cat_B` como base. As DIFERENÇAS por categoria entram via o
# cabeçalho dinâmico `_CAT_INFO` injetado no topo do prompt (vide _cat_header).
_CAT_DIR = {
    "A": "cat_B",
    "B": "cat_B",
    "C": "cat_B",
    "D": "cat_B",
    "E": "cat_B",
}

# Veículo + particularidades MBEDV por categoria. Override explícito da
# suposição "Cat B / carro" do base.md quando o exame é de outra categoria.
_CAT_INFO = {
    "A": (
        "Motocicleta, motoneta ou ciclomotor (2 rodas)",
        "- NÃO há cinto de segurança nem baliza de carro — não pontue por ausência deles.\n"
        "- Capacete devidamente afivelado é OBRIGATÓRIO (Art. 244 I — gravíssima, 6 pts); "
        "vestuário/equipamento conforme CONTRAN.\n"
        "- Avalie EQUILÍBRIO e domínio: pé no chão indevido em movimento, guidão instável, "
        "condução sem firmeza, parada sem apoiar corretamente.\n"
        "- A câmera 'interna' pode não existir como no carro — foque nas externas.",
    ),
    "B": (
        "Carro de passeio (4 rodas)",
        "- Regras da base aplicam-se diretamente (cinto, baliza/estacionamento, mãos ao volante).",
    ),
    "C": (
        "Veículo de carga / caminhão",
        "- Veículo longo e pesado: dimensões maiores, raio de manobra amplo, pontos cegos.\n"
        "- Baliza/estacionamento exigem mais espaço; avalie balanço e invasão de faixa em conversões.\n"
        "- Cinto e regras gerais da base continuam valendo.",
    ),
    "D": (
        "Veículo de transporte de passageiros / ônibus",
        "- Veículo longo: atenção a balanço traseiro em conversões e ao raio de giro.\n"
        "- Mesmo sendo Cat D, NÃO pode trafegar em faixa de uso EXCLUSIVO de ônibus durante o exame "
        "(MBEDV — não autorizado naquele local).\n"
        "- Cinto e regras gerais da base continuam valendo.",
    ),
    "E": (
        "Combinação de veículos com reboque/semirreboque (articulado)",
        "- Veículo ARTICULADO: manobras de ré e conversões com reboque; risco de 'efeito canivete'.\n"
        "- Baliza/estacionamento e balizamento traseiro são críticos; avalie controle do conjunto.\n"
        "- Cinto e regras gerais da base continuam valendo.",
    ),
}


def _cat_header(cat_key: str) -> str:
    """Cabeçalho que torna o prompt CIENTE da categoria real do exame,
    sobrepondo a suposição 'Cat B / carro' do base.md."""
    veiculo, partics = _CAT_INFO.get(cat_key, _CAT_INFO["B"])
    return (
        f"# ⚠️ EXAME DE CATEGORIA {cat_key} — {veiculo}\n\n"
        f"Este exame é da **Categoria {cat_key}**. A LÓGICA MBEDV (pontuação ≤10, "
        f"pesos 1/2/4/6, sem eliminatórias, 'in dubio pro reo') vale para TODAS as "
        f"categorias. As regras gerais abaixo foram redigidas com exemplos de Cat B "
        f"(carro), mas você deve julgar conforme a Categoria {cat_key}, observando:\n\n"
        f"{partics}\n\n"
        f"Quando uma regra abaixo for claramente específica de carro (Cat B) e não fizer "
        f"sentido para a Categoria {cat_key}, NÃO a aplique.\n"
        f"───────────────────────────────────────────────────────────────\n\n"
    )


# Câmera → arquivo cam_*.md
_CAM_FILE = {
    "frontal": "cam_frontal.md",
    "interna": "cam_interna.md",
    "lateral_direita": "cam_lateral_direita.md",
    "traseira_esq": "cam_traseira_esq.md",
}

# Ordem visual canônica (não influi na composição mas o composer respeita
# a ordem do CameraMap recebido).
_QUADRANT_ORDER: tuple[QuadrantName, ...] = ("TL", "TR", "BL", "BR")


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Fragment de prompt não encontrado: {path}")
    return path.read_text(encoding="utf-8")


def compose_system_prompt(categoria: str, camera_map: CameraMap | None) -> str:
    """Devolve o system prompt completo Cat <X> + 4 cam fragments.

    Argumentos:
      categoria: 'A' | 'B' | 'C' | 'D' | 'E'. Fallback pra 'B' se desconhecido.
      camera_map: resultado do `layout_discovery.discover_layout(...)`.
                  Pode ser None — nesse caso devolve só o base.md (sem cam
                  fragments) e o modelo se vira com a heurística do v25.

    Devolve a string de system prompt pronta pra Vertex AI `system_instruction`.
    """
    cat_key = (categoria or "B").upper()
    if cat_key not in _CAT_DIR:
        log.warning("Categoria '%s' desconhecida — usando cat_B como fallback", cat_key)
        cat_key = "B"

    cat_dir = PRESET_V26 / _CAT_DIR[cat_key]
    # Cabeçalho de categoria + base comum. O header torna o prompt ciente da
    # categoria real (a base.md é Cat-B-cêntrica).
    base = _cat_header(cat_key) + _read(cat_dir / "base.md")

    if camera_map is None or not camera_map.quadrantes:
        log.info("compose: sem camera_map — devolvendo só base.md (sem cam fragments)")
        return base

    parts = [base]
    parts.append("\n\n# Layout do vídeo (descoberto na Fase 1)\n")
    parts.append(
        f"Confiança do layout: {camera_map.confianca_layout:.2f} | "
        f"Fabricante: {camera_map.fabricante_provavel} | "
        f"Tipo: {camera_map.layout_detectado}\n"
    )

    for q in _QUADRANT_ORDER:
        info = camera_map.quadrantes.get(q)
        if info is None:
            continue
        camera = info.camera
        parts.append(
            f"\n\n═══════════════════════════════════════════════════════════════\n"
            f"## QUADRANTE {q} = câmera **{camera.upper()}**  "
            f"(confiança {info.confianca:.2f})\n"
            f"═══════════════════════════════════════════════════════════════\n"
        )
        if camera == "desconhecido":
            parts.append(
                f"O classificador de layout não identificou a câmera deste quadrante.\n"
                f'Descrição visual: "{info.descricao}"\n\n'
                f"Olhe e tente inferir. Se não conseguir, marque o campo "
                f"`layout_disagreement` no JSON com a sua melhor descrição."
            )
            continue
        cam_file = _CAM_FILE.get(camera)
        if cam_file is None:
            parts.append(
                f"Câmera '{camera}' não tem fragment definido. Use a heurística "
                f"geral da base.md pra esta vista."
            )
            continue
        parts.append(_read(cat_dir / cam_file))

    return "\n".join(parts)


def list_available_categories() -> list[str]:
    """Categorias com fragments REAIS (não fallback). Útil pra UI/diagnóstico."""
    return [k for k, v in _CAT_DIR.items() if (PRESET_V26 / v / "base.md").exists()]
