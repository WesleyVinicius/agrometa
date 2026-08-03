# AgroMeta

Framework de integração semântica que opera como um motor de triplificação (ETL Semântico) para harmonizar metadados agrometeorológicos. O projeto unifica dados biológicos (ocorrências de pragas), matrizes climáticas e metadados de proveniência em um Grafo de Conhecimento (RDF) interligado.

## Tecnologias
- Python, FastAPI
- RDFLib, Pandas, xml.etree
- Padrões de Metadados: ISO 19115, Darwin Core (DwC), WMO Core Metadata Profile (WCMP) v2
- Ontologias: AGROVOC (FAO), GeoSPARQL, SOSA, OWL-Time
- Protégé (HermiT Reasoner) e GraphDB

## Pré-requisitos
- Python 3.9+ instalado
- Gerenciador de pacotes `pip`
- Acesso à internet para requisições de desambiguação ao endpoint SPARQL oficial da FAO
- GraphDB (opcional, para visualização e execução de consultas lógicas no grafo resultante)

## Instalação

Clone o repositório para a sua máquina local:
```bash

git clone https://github.com/seu-usuario/agrometa.git
cd agrometa
```

Crie e ative o ambiente virtual:
```bash

# Linux/macOS
python -m venv venv
source venv/bin/activate

# Windows
venv\Scripts\activate
```

Instale as dependências do projeto:
```bash

pip install -r requirements.txt
```

## Como usar a API

O AgroMeta foi desenhado para ser consumido como um serviço. Siga os passos abaixo para iniciar o servidor e realizar a triplificação dos dados.

### 1. Iniciando o Servidor
Com o ambiente virtual ativado, inicie a API localmente a partir do arquivo principal:

```bash

uvicorn triplificador_api:app --reload
```

### 2. Uso via Interface Interativa (Swagger UI)
A forma mais rápida de testar a orquestração é utilizando a documentação interativa gerada automaticamente pelo FastAPI:
1. Acesse `[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)` no seu navegador.
2. Expanda o endpoint **POST** `/api/v1/triplificar/`.
3. Clique no botão **"Try it out"**.
4. Faça o upload dos arquivos de amostragem localizados na pasta `dados/`:
   - `biodiversidade_dwc`: selecione `occurrence.txt`
   - `catalogo_wcmp2`: selecione `metadados_wcmp2_inmet.json`
   - `observacoes_meteorologicas`: selecione o arquivo CSV do INMET
   - `proveniencia_iso19115`: selecione `dados_iso.xml`
5. Clique em **"Execute"**. O sistema processará as ontologias da pasta `ontologia/` e salvará o arquivo `.ttl` final automaticamente na pasta `resultados/`.

### 3. Uso via Requisição HTTP (Integração com outros sistemas)
Se você deseja consumir esta API a partir de outro sistema ou via terminal, pode realizar uma requisição `multipart/form-data`. Exemplo usando cURL:

```bash

curl -X 'POST' \
  'http://127.0.0.1:8000/api/v1/triplificar/' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'biodiversidade_dwc=@dados/occurrence.txt' \
  -F 'catalogo_wcmp2=@dados/metadados_wcmp2_inmet.json' \
  -F 'observacoes_meteorologicas=@dados/INMET_S_PR_A873_MORRETES.csv' \
  -F 'proveniencia_iso19115=@dados/dados_iso.xml'
```

## Testes e Validação
A base ontológica (`mapeamento-agrometa.owl`) foi validada nativamente no **Protégé** com testes de Verificação de Consistência e Classificação Automática via **HermiT**. 

Para rodar os testes analíticos práticos e Questões de Competência (CQs):
1. Importe o arquivo `grafo_final_api_integrated.ttl` (gerado na pasta `resultados/`) para o **GraphDB**.
2. Execute consultas **SPARQL** para testar correlações ambientais (ex: incidência de *Spodoptera frugiperda* sob estresse hídrico) e verificar a desambiguação terminológica alcançada.

## Estrutura do Projeto
```text
agrometa/
├── dados/                              # Arquivos brutos de amostragem (CSV, XML, JSON)
├── ontologia/                          # TBox: Modelagem semântica e regras de domínio
│   └── mapeamento-agrometa.owl         
├── resultados/                         # ABox: Resultados gerados dinamicamente pela API
├── requirements.txt                    # Dependências do projeto (FastAPI, RDFLib, Pandas, etc.)
├── triplificador_api.py                # Pipeline principal (ETL Semântico) e API RESTful
└── README.md
```

## Contribuindo
1. Faça o Fork do projeto
2. Crie sua Feature Branch (`git checkout -b feature/NovaIntegracao`)
3. Faça o Commit de suas alterações (`git commit -m 'Adiciona suporte à nova ontologia'`)
4. Faça o Push para a Branch (`git push origin feature/NovaIntegracao`)
5. Abra um Pull Request

## Licença
Este projeto está licenciado sob a Licença MIT.

## Autor
**Wesley Vinicius Fernandes**

- [LinkedIn](https://www.linkedin.com/in/wesleyviniciusf)
- [GitHub](https://github.com/WesleyVinicius)