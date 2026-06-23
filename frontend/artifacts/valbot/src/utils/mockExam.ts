const NOMES = [
  "Fernanda Souza",
  "Marcos Almeida",
  "Patrícia Rocha",
  "João Pereira",
  "Ana Lima",
  "Rafael Mendes",
  "Camila Ribeiro",
  "Bruno Cardoso",
  "Larissa Oliveira",
  "Gustavo Martins",
  "Juliana Ferreira",
  "Diego Carvalho",
  "Beatriz Costa",
  "Eduardo Silva",
  "Mariana Gomes",
  "Henrique Barbosa",
  "Renata Pinto",
  "Felipe Araújo",
  "Tatiana Moraes",
  "Lucas Nascimento",
];

const EXAMINADORES = [
  "Carlos Mendes",
  "Patricia Rocha",
  "Roberto Vieira",
  "Sandra Oliveira",
  "Fernando Castro",
  "Adriana Lopes",
  "Wagner Pires",
  "Elaine Tavares",
  "Marco Aurélio",
  "Cláudia Borges",
  "José Augusto",
  "Lúcia Helena",
  "Ricardo Nunes",
  "Vanessa Queiroz",
  "Antônio Faria",
];

const VEICULOS = [
  "Chevrolet Onix",
  "Hyundai HB20",
  "Volkswagen Gol",
  "Volkswagen Polo",
  "Toyota Yaris",
  "Fiat Argo",
  "Renault Kwid",
  "Ford Ka",
];

const CIDADES_SP = [
  "SP-Mooca",
  "SP-Tatuapé",
  "SP-Pinheiros",
  "SP-Lapa",
  "SP-Penha",
  "SP-Santana",
  "SP-Vila Mariana",
  "SP-Itaquera",
  "SP-Butantã",
  "SP-Ipiranga",
];

const ESCOLAS = [
  "Auto Escola Demo SP",
  "Auto Escola Brasil SP",
  "Auto Escola Paulista",
  "Auto Escola Aliança",
  "Auto Escola Volante",
  "Auto Escola Pioneira",
  "Auto Escola Modelo",
  "Auto Escola Tradição",
  "Auto Escola Avenida",
  "Auto Escola Capital",
];

const PLACA_PREFIXOS = ["ABC", "DEF", "GHI", "JKL", "MNO", "PQR", "STU"];

const pick = <T,>(a: readonly T[]): T => a[Math.floor(Math.random() * a.length)];

const num = (n: number): string =>
  String(Math.floor(Math.random() * 10 ** n)).padStart(n, "0");

export type TrainingAnnotation = {
  /** Offset dentro do vídeo no formato HH:MM:SS (ex: "00:02:35"). */
  timestamp: string;
  /** Texto livre da anotação. */
  anotacoes: string;
};

export type ExamDefaults = {
  candidato_nome: string;
  candidato_cpf: string;
  renach: string;
  processo: string;
  categoria: string;
  veiculo: string;
  local: string;
  examinador: string;
  auto_escola: string;
  rubrica: "1020/2025" | "789/2020";
  training_annotations: TrainingAnnotation[];
};

export function generateRandomExamDefaults(): ExamDefaults {
  return {
    candidato_nome: pick(NOMES),
    candidato_cpf: `***.${num(3)}.***-**`,
    renach: `SP-${num(8)}`,
    processo: `2024-${num(4)}`,
    categoria: pick(["B", "D"]),
    veiculo: `${pick(VEICULOS)} (${pick(PLACA_PREFIXOS)}-${num(4)})`,
    local: pick(CIDADES_SP),
    examinador: pick(EXAMINADORES),
    auto_escola: pick(ESCOLAS),
    rubrica: "1020/2025",
    training_annotations: [],
  };
}
