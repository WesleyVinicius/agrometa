import os
import json
import pandas as pd
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from rdflib import Graph, Namespace, URIRef, Literal, RDF, XSD

# Inicializa a API
app = FastAPI(
    title="AgroMeta Framework API",
    description="API REST para triplificação, resolução e integração semântica agrometeorológica.",
    version="1.0.0"
)

# Configuração de Namespaces e Constantes
BASE_URI = "http://agrometa-framework.org/"
DWC = Namespace("http://rs.tdwg.org/dwc/terms/")
WCMP2 = Namespace("http://wmo-im.github.io/wcmp2/")
ISO19115 = Namespace("http://www.isotc211.org/2005/gmd/")
SOSA = Namespace("http://www.w3.org/ns/sosa/")
GEO = Namespace("http://www.opengis.net/ont/geosparql#")
TIME = Namespace("http://www.w3.org/2006/time#")
AGRO = Namespace("http://aims.fao.org/aos/agrontology#")
AGROMETA = Namespace("http://agrometa-framework.org/ontology/agrometa#")

CACHE_RESOLVER_AGROVOC = {}
CACHE_RELACOES_AGROVOC = {}


# ==========================================
# FUNÇÕES DE DESAMBIGUAÇÃO (AGROVOC)
# ==========================================

def buscar_uri_agrovoc_automatico(nome_cientifico: str) -> str:
    """Busca a URI do AGROVOC corrigindo codificação e idioma"""
    partes = nome_cientifico.replace('J.E.', '').split(',')
    palavras = partes[0].strip().split(' ')
    nome_limpo = " ".join(palavras[:2]) if len(palavras) >= 2 else palavras[0]

    if nome_limpo in CACHE_RESOLVER_AGROVOC:
        return CACHE_RESOLVER_AGROVOC[nome_limpo]

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Accept': 'application/json'}

    try:
        params = urllib.parse.urlencode({'query': nome_limpo})
        url = f"https://agrovoc.fao.org/agrovoc/rest/v1/search?{params}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data and data.get('results'):
                uri_fao = data['results'][0].get('uri')
                if uri_fao:
                    CACHE_RESOLVER_AGROVOC[nome_limpo] = uri_fao
                    return uri_fao
    except Exception:
        pass

    try:
        query = f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?uri WHERE {{
            ?uri skos:prefLabel|skos:altLabel ?label .
            FILTER (strstarts(lcase(str(?label)), "{nome_limpo.lower()}"))
        }} LIMIT 1
        """
        params = urllib.parse.urlencode({'query': query, 'format': 'json'})
        url = f"https://agrovoc.fao.org/sparql?{params}"
        req = urllib.request.Request(url,
                                     headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/sparql-results+json'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            bindings = data.get('results', {}).get('bindings', [])
            if bindings:
                uri_fao = bindings[0]['uri']['value']
                CACHE_RESOLVER_AGROVOC[nome_limpo] = uri_fao
                return uri_fao
    except Exception:
        pass

    uri_local = f"http://agrometa-framework.org/taxonomy/{nome_limpo.lower().replace(' ', '_')}"
    CACHE_RESOLVER_AGROVOC[nome_limpo] = uri_local
    return uri_local


def obter_relacoes_afetacao(uri_praga: str):
    """Consulta dinamicamente as afetações da praga de forma segura e limpa"""
    if not uri_praga.startswith("http://aims.fao.org/aos/agrovoc"):
        return []

    if uri_praga in CACHE_RELACOES_AGROVOC:
        return CACHE_RELACOES_AGROVOC[uri_praga]

    try:
        query = f"""
        SELECT DISTINCT ?cultura WHERE {{
            {{ <{uri_praga}> <http://aims.fao.org/aos/agrontology#affects> ?cultura . }}
            UNION
            {{ <{uri_praga}> <http://aims.fao.org/aos/agrontology#isPestOf> ?cultura . }}
            UNION
            {{ <{uri_praga}> <http://aims.fao.org/aos/agrontology#afflicts> ?cultura . }}
            UNION
            {{ ?cultura <http://aims.fao.org/aos/agrontology#hasPest> <{uri_praga}> . }}
            UNION
            {{ <{uri_praga}> <http://aims.fao.org/aos/agrontology#hasHost> ?cultura . }}
        }}
        """
        params = urllib.parse.urlencode({'query': query, 'format': 'json'})
        url = f"https://agrovoc.fao.org/sparql?{params}"
        req = urllib.request.Request(url,
                                     headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/sparql-results+json'})

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            culturas = [res['cultura']['value'] for res in data['results']['bindings']]
            CACHE_RELACOES_AGROVOC[uri_praga] = culturas
            return culturas
    except Exception as e:
        print(f"Aviso interno: Falha ao buscar cultura na FAO para {uri_praga} - {str(e)}")
        return []


# ==========================================
# FUNÇÕES DE MÓDULOS DE DOMÍNIO (ETL SEMÂNTICO)
# ==========================================

def inicializar_grafo():
    g = Graph()
    g.bind("rdf", RDF)
    g.bind("dwc", DWC)
    g.bind("sosa", SOSA)
    g.bind("geo", GEO)
    g.bind("time", TIME)
    g.bind("wcmp2", WCMP2)
    g.bind("iso19115", ISO19115)
    g.bind("agro", AGRO)
    g.bind("agrometa", AGROMETA)
    return g


def processar_biodiversidade(df_gbif, meu_grafo):
    for _, row in df_gbif.iterrows():
        gbif_id = str(row['gbifID'])
        occurrence_uri = URIRef(BASE_URI + f"biodiversity/occurrence_{gbif_id}")
        geom_uri = URIRef(BASE_URI + f"spatial/geom_{gbif_id}")

        meu_grafo.add((occurrence_uri, RDF.type, DWC.Occurrence))
        meu_grafo.add((occurrence_uri, RDF.type, GEO.Feature))
        meu_grafo.add((geom_uri, RDF.type, GEO.Geometry))

        nome_cientifico_str = str(row['scientificName']).strip()
        meu_grafo.add((occurrence_uri, AGROMETA.hasScientificName, Literal(nome_cientifico_str, datatype=XSD.string)))

        lat, lon = float(row['decimalLatitude']), float(row['decimalLongitude'])
        meu_grafo.add((occurrence_uri, AGROMETA.hasLatitude, Literal(lat, datatype=XSD.float)))
        meu_grafo.add((occurrence_uri, AGROMETA.hasLongitude, Literal(lon, datatype=XSD.float)))

        wkt_ponto = f"POINT({lon} {lat})"
        meu_grafo.add((occurrence_uri, GEO.hasGeometry, geom_uri))
        meu_grafo.add((geom_uri, GEO.asWKT, Literal(wkt_ponto, datatype=GEO.wktLiteral)))

        if pd.notna(row['eventDate']):
            meu_grafo.add(
                (occurrence_uri, AGROMETA.hasEventDate, Literal(str(row['eventDate'])[:10], datatype=XSD.string)))

        uri_final_vocabulo = buscar_uri_agrovoc_automatico(nome_cientifico_str)
        uri_agrovoc = URIRef(uri_final_vocabulo)
        meu_grafo.add((occurrence_uri, AGROMETA.hasAgrovocTerm, uri_agrovoc))

        culturas_afetadas = obter_relacoes_afetacao(str(uri_agrovoc))
        for cultura in culturas_afetadas:
            meu_grafo.add((uri_agrovoc, AGRO.affects, URIRef(cultura)))


def processar_meteorologia(meta_json, df_inmet, meu_grafo):
    dataset_id = meta_json['id']
    dataset_uri = URIRef(f"http://agrometa-framework.org/meteorology/{dataset_id}")

    meu_grafo.add((dataset_uri, RDF.type, WCMP2.Record))
    meu_grafo.add(
        (dataset_uri, AGROMETA.hasObservedProperty, Literal(meta_json['properties']['title'], datatype=XSD.string)))
    meu_grafo.add((dataset_uri, WCMP2.dataPolicy,
                   Literal(meta_json['properties'].get('wmo:dataPolicy', 'core'), datatype=XSD.string)))

    col_data, col_chuva = df_inmet.columns[0], df_inmet.columns[2]
    df_inmet[col_data] = df_inmet[col_data].astype(str).str.replace('/', '-')
    df_inmet[col_chuva] = pd.to_numeric(df_inmet[col_chuva].astype(str).str.replace(',', '.'), errors='coerce')
    df_inmet = df_inmet[df_inmet[col_chuva] != -9999.0]
    df_diario = df_inmet.groupby(col_data)[col_chuva].sum().reset_index()

    for _, row in df_diario.iterrows():
        data_string = str(row[col_data])
        obs_uri = URIRef(f"http://agrometa-framework.org/meteorology/observation_{data_string}")
        meu_grafo.add((obs_uri, RDF.type, SOSA.Observation))
        meu_grafo.add((obs_uri, AGROMETA.hasEventDate, Literal(data_string, datatype=XSD.string)))
        meu_grafo.add((obs_uri, AGROMETA.hasPrecipitationValue, Literal(float(row[col_chuva]), datatype=XSD.float)))
        meu_grafo.add((obs_uri, AGROMETA.hasStationID, Literal("API_GENERATED_STATION", datatype=XSD.string)))
        meu_grafo.add((dataset_uri, AGROMETA.hasObservationMember, obs_uri))

    return dataset_uri


def processar_proveniencia(tree, meu_grafo):
    root = tree.getroot()
    ns = {'gmd': 'http://www.isotc211.org/2005/gmd', 'gco': 'http://www.isotc211.org/2005/gco'}

    file_id_node = root.find('.//gmd:fileIdentifier/gco:CharacterString', ns)
    file_id = file_id_node.text.strip() if file_id_node is not None else "metadata_via_api"
    metadata_uri = URIRef(BASE_URI + f"institution/metadata_{file_id}")

    meu_grafo.add((metadata_uri, RDF.type, ISO19115.MD_Metadata))
    meu_grafo.add((metadata_uri, RDF.type, GEO.Feature))

    org_nodes = root.findall('.//gmd:organisationName/gco:CharacterString', ns)
    org_name = "Instituição Não Especificada"
    for node in org_nodes:
        if node.text and node.text.strip():
            org_name = node.text.strip()
            break
    meu_grafo.add((metadata_uri, AGROMETA.hasInstitution, Literal(org_name, datatype=XSD.string)))

    statement_node = root.find('.//gmd:LI_Lineage/gmd:statement/gco:CharacterString', ns)
    if statement_node is not None and statement_node.text:
        lineage_text = " ".join(statement_node.text.split())
        meu_grafo.add((metadata_uri, AGROMETA.hasLineage, Literal(lineage_text, datatype=XSD.string)))

    return metadata_uri


def tecer_elos_semanticos(meu_grafo, registro_meteorologico_uri, metadata_uri):
    """Cruza as instâncias geradas ligando o contexto climático e institucional à ocorrência"""
    for ocorrencia in meu_grafo.subjects(RDF.type, DWC.Occurrence):
        meu_grafo.add((ocorrencia, AGROMETA.hasMeteorologicalRecord, registro_meteorologico_uri))
        meu_grafo.add((ocorrencia, AGROMETA.hasClimaticContext, metadata_uri))


# ==========================================
# ENDPOINT DE ORQUESTRAÇÃO
# ==========================================

@app.post("/api/v1/triplificar/")
async def gerar_grafo_conhecimento(
        biodiversidade_dwc: UploadFile = File(...),
        catalogo_wcmp2: UploadFile = File(...),
        observacoes_meteorologicas: UploadFile = File(...),
        proveniencia_iso19115: UploadFile = File(...)
):
    try:
        # 1. Leitura de dados brutos
        df_gbif = pd.read_csv(biodiversidade_dwc.file, sep='\t', low_memory=False)
        meta_json = json.load(catalogo_wcmp2.file)
        df_inmet = pd.read_csv(observacoes_meteorologicas.file, sep=';', skiprows=8, encoding='iso-8859-1')
        tree = ET.parse(proveniencia_iso19115.file)

        # 2. Inicialização do grafo e parse da TBox
        meu_grafo = inicializar_grafo()
        caminho_ontologia = os.path.join("ontologia", "mapeamento-agrometa.owl")
        if os.path.exists(caminho_ontologia):
            meu_grafo.parse(caminho_ontologia, format="xml")

        # 3. Processamento modularizado (ETL Semântico)
        processar_biodiversidade(df_gbif, meu_grafo)
        dataset_uri = processar_meteorologia(meta_json, df_inmet, meu_grafo)
        metadata_uri = processar_proveniencia(tree, meu_grafo)
        tecer_elos_semanticos(meu_grafo, dataset_uri, metadata_uri)

        # 4. Serialização e Entrega do arquivo físico
        os.makedirs("resultados", exist_ok=True)
        arquivo_saida = os.path.join("resultados", "grafo_final_api_integrated.ttl")
        meu_grafo.serialize(destination=arquivo_saida, format="turtle")
        grafo_conteudo_turtle = meu_grafo.serialize(format="turtle")

        return JSONResponse(content={
            "status": "Sucesso",
            "mensagem": "Grafo de conhecimento gerado com harmonização semântica de afetação em tempo real.",
            "total_triplas_processadas": len(meu_grafo),
            "arquivo_gerado_no_servidor": arquivo_saida,
            "grafo_rdf_turtle": grafo_conteudo_turtle
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no pipeline de triplificação: {str(e)}")