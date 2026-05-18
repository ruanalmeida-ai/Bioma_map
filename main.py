import streamlit as st
import ee
import geopandas as gpd
import pandas as pd
# Bibliotecas de Geovisualização
try:
    # Usando foliumap para garantir compatibilidade com Folium para persistência
    import geemap.foliumap as geemap 
except Exception:
    import geemap as geemap

# Bibliotecas adicionadas para suportar a lógica de desenho do usuário
try:
    import folium
    from streamlit_folium import st_folium
    import folium.plugins
except ImportError:
    st.error("Instale 'folium' e 'streamlit-folium' para usar o desenho de ROI.")
    raise

import plotly.express as px
import json
import os
import base64
import tempfile
import shutil
from io import BytesIO
from shapely import wkb 
import numpy as np


# =========================================================
# FUNÇÃO SEGURA PARA REMOVER CAMADAS
# =========================================================
def remove_layers_by_prefix(map_obj, prefix):

    try:

        # Compatível com diferentes versões do geemap/folium
        if hasattr(map_obj, "_children"):

            keys_to_remove = []

            for key, layer in list(map_obj._children.items()):

                if hasattr(layer, "name"):

                    layer_name = str(layer.name)

                    if layer_name.startswith(prefix):
                        keys_to_remove.append(key)

            # Remove layers encontradas
            for key in keys_to_remove:
                del map_obj._children[key]

    except Exception as e:

        st.warning(f"Erro ao remover camadas: {e}")


# --- Configurações Iniciais e Inicialização do Earth Engine ---

# ID do Projeto Cloud (Ajuste conforme necessário)
CLOUD_PROJECT_ID = 'aulasgeee-477119'

# Configurações do Streamlit
st.set_page_config(layout="wide", page_title="MapBiomas LULC Temporal")

@st.cache_resource(ttl=None)
def initialize_ee():
    """Inicializa o Google Earth Engine usando Service Account via secrets ou arquivo local."""
    st.info("Carregando Google Earth Engine...")
    temp_path = None
    try:
        secrets_bucket = st.secrets.get("google_earth_engine") if hasattr(st, "secrets") else None
        if secrets_bucket and secrets_bucket.get("service_account_b64"):
            b64 = secrets_bucket["service_account_b64"]
            decoded = base64.b64decode(b64)
            with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".json") as tf:
                tf.write(decoded)
                temp_path = tf.name
            with open(temp_path, "r", encoding="utf-8") as f:
                key_data = json.load(f)
            credentials = ee.ServiceAccountCredentials(key_data["client_email"], temp_path)
            ee.Initialize(credentials=credentials, project=key_data.get("project_id", CLOUD_PROJECT_ID))
            st.success("Google Earth Engine inicializado via secrets.")
            return ee

        # Fallback: arquivo local service_account.json
        json_path = os.path.join(os.getcwd(), "service_account.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                key_data = json.load(f)
            credentials = ee.ServiceAccountCredentials(key_data["client_email"], json_path)
            ee.Initialize(credentials=credentials, project=key_data.get("project_id", CLOUD_PROJECT_ID))
            st.success("Google Earth Engine inicializado via arquivo local.")
            return ee

        st.error("❌ Credenciais não encontradas em secrets nem em service_account.json.")
        return None
    except Exception as e:
        st.error(f"⚠️ Erro fatal na inicialização do GEE: {e}")
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


# --- Definições de Variáveis, Paletas e Legenda ---

# Variáveis de Estado
if "ano_atual" not in st.session_state: st.session_state["ano_atual"] = 2024
if "ano_inicial" not in st.session_state: st.session_state["ano_inicial"] = 2000
st.session_state["collection"] = "MapBiomas LULC Coleção 9 (30m)"
if "geojson_roi" not in st.session_state: st.session_state["geojson_roi"] = None
if "stats_df" not in st.session_state: st.session_state["stats_df"] = None
if "roi_geometry_data" not in st.session_state: st.session_state["roi_geometry_data"] = None 
if "roi_source" not in st.session_state: st.session_state["roi_source"] = "Nenhuma"
if "geemap_map_object" not in st.session_state: st.session_state["geemap_map_object"] = None 
if "transition_df" not in st.session_state: st.session_state["transition_df"] = None 
if "enable_transition" not in st.session_state: st.session_state["enable_transition"] = False


# Parâmetros MapBiomas
# Paleta completa (MapBiomas Color Table) - Usada para o mapa EE
lulc_palette = ["#ffffff", "#32a65e", "#32a65e", "#1f8d49", "#7dc975", "#04381d", "#026975", "#000000", "#000000", "#7a6c00", "#ad975a", "#519799", "#d6bc74", "#d89f5c", "#FFFFB2", "#edde8e", "#000000", "#000000", "#f5b3c8", "#C27BA0", "#db7093", "#ffefc3", "#db4d4f", "#ffa07a", "#d4271e", "#db4d4f", "#0000FF", "#000000", "#000000", "#ffaa5f", "#9c0027", "#091077", "#fc8114", "#2532e4", "#93dfe6", "#9065d0", "#d082de", "#000000", "#000000", "#f5b3c8", "#c71585", "#f54ca9", "#cca0d4", "#dbd26b", "#807a40", "#e04cfa", "#d68fe2", "#9932cc", "#e6ccff", "#02d659", "#ad5100", "#000000", "#000000", "#000000", "#000000", "#000000", "#000000", "#CC66FF", "#FF6666", "#006400", "#8d9e8b", "#f5d5d5", "#ff69b4", "#ebf8b5", "#000000", "#000000", "#91ff36", "#7dc975", "#e97a7a", "#0fffe3"]
lulc_vis_params = {'min': 0, 'max': 69, 'palette': lulc_palette}


# 🎯 DICIONÁRIO DE LEGENDAS (Seu Input)
legenda_nome_mapbiomas = {
    1: "Floresta", 3: "Formação Florestal", 4: "Formação Savânica",
    5: "Mangue", 6: "Floresta Alagável", 49: "Restinga Arbórea",
    10: "Vegetação Herbácea e Arbustiva", 11: "Campo Alagado / Pantanosa",
    12: "Formação Campestre", 32: "Apicum", 29: "Afloramento Rochoso",
    50: "Restinga Herbácea", 14: "Agropecuária", 15: "Pastagem",
    18: "Agricultura", 19: "Lavoura Temporária", 39: "Soja", 20: "Cana",
    40: "Arroz", 62: "Algodão (beta)", 41: "Outras Lavouras Temporárias",
    36: "Lavoura Perene", 46: "Café", 47: "Citrus", 35: "Dendê",
    48: "Outras Lavouras Perenes", 9: "Silvicultura", 21: "Mosaico de Usos",
    22: "Área não Vegetada", 23: "Praia, Duna e Areal", 24: "Área Urbanizada",
    30: "Mineração", 25: "Outras Áreas não Vegetadas", 26: "Corpo D'água",
    33: "Rio, Lago e Oceano", 31: "Aquicultura", 27: "Não Observado"
}

# --- RECRIAÇÃO DA ESTRUTURA DATAFRAME COM CORES PARA PLOTLY ---

# Mapeia as classes do dicionário para a paleta MapBiomas completa.
mapbiomas_cores = {
    i: lulc_palette[i] for i in legenda_nome_mapbiomas.keys() if i < len(lulc_palette)
}

# Constrói o DataFrame base a partir do dicionário de nomes
legenda_base = pd.DataFrame(
    legenda_nome_mapbiomas.items(), 
    columns=['Classe', 'Nome']
)
legenda_base['Cor'] = legenda_base['Classe'].map(mapbiomas_cores).fillna("#888888")


# Cria a tabela de mapeamento completa (Garante todas as classes e preenchimento)
legenda_completa = pd.DataFrame([
    {"Classe": c, "Nome": f"Classe {c}", "Cor": "#CCCCCC"} for c in range(1, 70)
]).merge(legenda_base, on=["Classe"], how="left", suffixes=('_default', None))

# Usa o nome e cor definidos no dicionário (se houver) ou mantém o padrão
legenda_completa['Nome'] = legenda_completa['Nome'].fillna(legenda_completa['Nome_default'])
legenda_completa['Cor'] = legenda_completa['Cor'].fillna("#888888")

# Converte a Classe para Inteiro para garantir o merge perfeito
legenda_completa['Classe'] = legenda_completa['Classe'].astype(int)

# DataFrame final que será usado na função de análise
legenda_mapbiomas = legenda_completa.drop_duplicates(subset=['Classe'])


# --- Funções de Processamento ---

def to_excel(df, sheet_name): 
    output = BytesIO()
    # Usa openpyxl para evitar dependência de xlsxwriter
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    processed_data = output.getvalue()
    return processed_data

def to_excel_multi(sheets_dict):
    """Exporta múltiplos DataFrames em um único Excel (openpyxl)."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for name, df in sheets_dict.items():
            if df is None or df is ...:
                continue
            safe_df = df.copy()
            safe_df.to_excel(writer, index=False, sheet_name=str(name)[:31])
    return output.getvalue()

@st.cache_data(max_entries=10, ttl=300)
def read_and_convert_geojson_shp_kml(uploaded_files): 
    if not uploaded_files: return None, "Nenhum arquivo enviado."
    main_file = next((f for f in uploaded_files if f.name.lower().endswith(('.geojson', '.kml', '.shp'))), None)
    if main_file is None: return None, "O upload deve incluir um arquivo .geojson, .shp ou .kml principal."

    temp_dir = None
    try:
        ext = main_file.name.lower().split('.')[-1]
        gdf = None
        
        if ext == 'geojson':
            geojson_data = json.load(main_file)
            gdf = gpd.GeoDataFrame.from_features(normalize_geojson(geojson_data)["features"], crs="EPSG:4326")
        elif ext in ('shp', 'kml', 'zip'):
            temp_dir = tempfile.mkdtemp()
            for f in uploaded_files:
                temp_path = os.path.join(temp_dir, f.name)
                with open(temp_path, 'wb') as out: out.write(f.getvalue())
            
            main_path = next((os.path.join(temp_dir, f.name) for f in uploaded_files if f.name.endswith('.shp')), 
                             os.path.join(temp_dir, main_file.name))
            gdf = gpd.read_file(main_path)
        
        # Garante que o CRS está definido antes de transformar
        if gdf.crs is None:
            gdf.set_crs(epsg=4326, inplace=True)
        else:
            gdf = gdf.to_crs(epsg=4326)
        def remove_z(geom):
            if geom and geom.has_z: return wkb.loads(wkb.dumps(geom, output_dimension=2)) 
            return geom
        gdf['geometry'] = gdf.geometry.apply(remove_z).buffer(0)
        gdf = gdf[~gdf.geometry.is_empty].dropna(subset=['geometry'])
        if gdf.empty: return None, "O arquivo foi lido, mas não contém geometrias válidas após a limpeza."

        return json.loads(gdf.to_json()), f"Arquivo .{ext} convertido e limpo (2D) com sucesso."
            
    except Exception as e: return None, f"Erro na conversão: {e}"
    finally:
        if temp_dir and os.path.exists(temp_dir): shutil.rmtree(temp_dir)

def normalize_geojson(obj): 
    if isinstance(obj, dict):
        if obj.get('type') == 'FeatureCollection': return obj
        elif obj.get('type') == 'Feature': return {"type": "FeatureCollection", "features": [obj]}
        elif obj.get('type') in ['Polygon', 'LineString', 'Point', 'MultiPolygon', 'MultiLineString', 'MultiPoint']:
            return {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": obj, "properties": {}}]}
    return {"type": "FeatureCollection", "features": []}

def get_map_image(year, roi=None): 
    image_id = "projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1"
    image = ee.Image(image_id).select(f"classification_{year}")
    params = lulc_vis_params
    layer_name = f'MapBiomas Col 9 - {year} (30m)'
    
    if roi: image = image.clip(roi.geometry().dissolve(maxError=10))
    return image, params, layer_name

def add_ee_layer_compat(map_obj, ee_object, vis_params, name, shown=True, opacity=1.0): 
    try:
        if hasattr(map_obj, 'add_ee_layer'): 
             return map_obj.add_ee_layer(ee_object, vis_params, name, shown, opacity)
        if hasattr(map_obj, 'addLayer'): 
             return map_obj.addLayer(ee_object, vis_params, name)
    except Exception as e:
        st.error(f"Não foi possível adicionar camada EE ao mapa: {e}")
        return None

def process_single_year_analysis(ee_feature_collection, current_ano): 
    image_id = "projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1"
    lulc_image = ee.Image(image_id).select(f"classification_{current_ano}")
    
    try:
        roi_geometry = ee_feature_collection.geometry().dissolve(maxError=10)
        pixel_area = ee.Image.pixelArea().divide(1e4)  # ha
        image_area = pixel_area.addBands(lulc_image)
        
        area_por_classe = image_area.reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName='class'),
            geometry=roi_geometry,
            scale=30,
            maxPixels=1e13
        )

        stats = area_por_classe.getInfo()
        grupos = stats.get('groups', [])
        df = pd.DataFrame(grupos)
        
        if df.empty or 'sum' not in df.columns or 'class' not in df.columns:
            st.warning("A redução de área não retornou dados de 'sum' ou 'class'. Verifique se a ROI cruza a área de dados.")
            return pd.DataFrame(), None, None

        df = df.rename(columns={"class": "Classe", "sum": "Área (ha)"})
        
        # Garante que a coluna 'Classe' seja um inteiro antes de mesclar
        df["Classe"] = df["Classe"].astype(int) 
        
        df["Área (ha)"] = df["Área (ha)"].round(2)
        df = df.sort_values("Área (ha)", ascending=False)
        
        # Mescla com a tabela de legenda
        df = df.merge(legenda_mapbiomas[["Classe", "Nome", "Cor"]], on="Classe", how="left")
        
        # Preenche Nomes e Cores ausentes
        df['Nome'] = df['Nome'].fillna(df['Classe'].apply(lambda x: f'Classe {x} (Sem Nome)')).astype(str)
        df['Cor'] = df['Cor'].fillna("#888888") 
        
        roi_geojson = json.dumps(roi_geometry.getInfo())

        return df, roi_geojson, lulc_image.clip(roi_geometry)

    except Exception as e:
        st.error(f"Erro na análise de área MapBiomas: {e}")
        return None, None, None

def area_by_class_for_year(ee_feature_collection, ano, exclude_class_27=False):
    """Calcula área por classe para um ano específico dentro da ROI.
    Retorna DataFrame com colunas: Classe, Nome, Área (ha).
    """
    image_id = "projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1"
    lulc_image = ee.Image(image_id).select(f"classification_{ano}").unmask(27)
    try:
        roi_geometry = ee_feature_collection.geometry().dissolve(maxError=10)
        pixel_area = ee.Image.pixelArea().divide(1e4)
        image_area = pixel_area.addBands(lulc_image)
        area_por_classe = image_area.reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName='class'),
            geometry=roi_geometry,
            scale=30,
            maxPixels=1e13,
            tileScale=4
        )
        stats = area_por_classe.getInfo()
        grupos = stats.get('groups', [])
        df = pd.DataFrame(grupos)
        if df.empty or 'sum' not in df.columns or 'class' not in df.columns:
            return pd.DataFrame(columns=['Classe','Nome','Área (ha)'])
        df = df.rename(columns={'class':'Classe','sum':'Área (ha)'})
        df['Classe'] = df['Classe'].astype(int)
        if exclude_class_27:
            df = df[df['Classe'] != 27]
        df['Área (ha)'] = df['Área (ha)'].round(2)
        df = df.merge(legenda_mapbiomas[['Classe','Nome','Cor']], on='Classe', how='left')
        df['Nome'] = df['Nome'].fillna(df['Classe'].apply(lambda x: f'Classe {x}'))
        df['Cor'] = df['Cor'].fillna('#888888')
        return df[['Classe','Nome','Cor','Área (ha)']]
    except Exception:
        return pd.DataFrame(columns=['Classe','Nome','Cor','Área (ha)'])

def process_transition_analysis(ee_feature_collection, year_initial, year_final):
    image_id = "projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1"
    
    # Garante banda presente e preenche não observados com 27 para evitar máscara nula
    image_i = ee.Image(image_id).select(f"classification_{year_initial}").unmask(27)
    image_f = ee.Image(image_id).select(f"classification_{year_final}").unmask(27)
    
    try:
        roi_geometry = ee_feature_collection.geometry().dissolve(maxError=10)
        pixel_area = ee.Image.pixelArea().divide(1e4)  # ha

        # Cria o código de transição: (classe_inicial * 100) + classe_final
        transition_code = image_i.multiply(100).add(image_f).rename('transition_code')

        # A regra do reducer: entradas ponderadas (área) DEVEM vir antes da banda de agrupamento.
        # Portanto, a banda 0 é 'area' e a banda 1 é 'transition_code'.
        combined = pixel_area.rename('area').addBands(transition_code)

        # Soma a área (banda 0) agrupando pelo código de transição (groupField=1)
        transition_stats = combined.reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName='transition_code'),
            geometry=roi_geometry,
            scale=30,
            maxPixels=1e13,
            tileScale=4
        )
        
        stats_info = transition_stats.getInfo()
        
        data = []
        for g in stats_info.get('groups', []):
            code = int(g.get('group', 0))
            area = float(g.get('sum', 0.0))
            
            # Decodifica o código de transição:
            initial_class = code // 100
            final_class = code % 100
            
            data.append({
                'Classe Inicial': initial_class,
                'Classe Final': final_class,
                'Área (ha)': round(area, 2)
            })

        df_transition = pd.DataFrame(data)
        if df_transition.empty: return pd.DataFrame()

        df_transition['Classe Inicial'] = df_transition['Classe Inicial'].astype(int)
        df_transition['Classe Final'] = df_transition['Classe Final'].astype(int)

        df_transition = df_transition.merge(
            legenda_mapbiomas[['Classe', 'Nome']].rename(columns={'Classe': 'Classe Inicial', 'Nome': 'Nome Inicial'}),
            on='Classe Inicial', how='left'
        )
        df_transition = df_transition.merge(
            legenda_mapbiomas[['Classe', 'Nome']].rename(columns={'Classe': 'Classe Final', 'Nome': 'Nome Final'}),
            on='Classe Final', how='left'
        )

        return df_transition.fillna({'Nome Inicial': 'Não Observado', 'Nome Final': 'Não Observado'})

    except Exception as e:
        st.error(f"Erro na análise de transição MapBiomas: {e}")
        return None

def compute_change_area(ee_feature_collection, year_initial, year_final):
    """Calcula área de mudança (classes diferentes) excluindo pixels Não Observado (27)."""
    image_id = "projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1"
    image_i = ee.Image(image_id).select(f"classification_{year_initial}").unmask(27)
    image_f = ee.Image(image_id).select(f"classification_{year_final}").unmask(27)
    roi_geometry = ee_feature_collection.geometry().dissolve(maxError=10)

    # Máscara: somente pixels observados e que mudaram
    observed_mask = image_i.neq(27).And(image_f.neq(27))
    change_mask = image_i.neq(image_f).And(observed_mask)
    change_area = ee.Image.pixelArea().divide(1e4).updateMask(change_mask)

    change_stats = change_area.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=roi_geometry,
        scale=30,
        maxPixels=1e13,
        tileScale=4
    )
    try:
        result = change_stats.getInfo()
        val = result.get('area', 0.0)
    except Exception:
        val = 0.0
    return float(val)

@st.cache_data(max_entries=5, ttl=600)
def area_time_series(_ee_feature_collection, years, roi_hash=None):
    """Calcula série temporal de área por classe para os anos informados, excluindo classe 27, processando em lotes.
    roi_hash: string hashável para diferenciar ROIs no cache."""
    image_id = "projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1"
    try:
        roi_geometry = _ee_feature_collection.geometry().dissolve(maxError=10)
        
        # Processa os anos em lotes para evitar "Too many concurrent aggregations"
        batch_size = 5  # Processa 5 anos por vez
        years_list = list(years)
        all_data = []
        
        for batch_start in range(0, len(years_list), batch_size):
            batch_end = min(batch_start + batch_size, len(years_list))
            batch_years = years_list[batch_start:batch_end]
            years_batch = ee.List(batch_years)

            def per_year(y):
                y = ee.Number(y)
                band_name = ee.String('classification_').cat(y.format())
                img = ee.Image(image_id).select(band_name).unmask(27)
                area_img = ee.Image.pixelArea().divide(1e4).addBands(img)
                res = area_img.reduceRegion(
                    reducer=ee.Reducer.sum().group(groupField=1, groupName='class'),
                    geometry=roi_geometry,
                    scale=30,
                    maxPixels=1e13,
                    tileScale=4,
                    bestEffort=True
                )
                groups = ee.List(ee.Dictionary(res).get('groups', ee.List([])))

                def to_feat(g):
                    d = ee.Dictionary(g)
                    return ee.Feature(None, {
                        'Ano': y,
                        'Classe': d.get('class'),
                        'Área (ha)': d.get('sum')
                    })

                return ee.FeatureCollection(groups.map(to_feat))

            # Processa este lote
            fc_batch = ee.FeatureCollection(years_batch.map(per_year)).flatten()
            data_batch = fc_batch.getInfo().get('features', [])
            all_data.extend(data_batch)
        
        if not all_data:
            return pd.DataFrame(columns=['Ano','Classe','Nome','Cor','Área (ha)']), "Nenhum dado retornado do Earth Engine. Verifique se a ROI está dentro da área mapeada pelo MapBiomas."

        rows = [f.get('properties', {}) for f in all_data]
        df = pd.DataFrame(rows)
        
        if df.empty:
            return pd.DataFrame(columns=['Ano','Classe','Nome','Cor','Área (ha)']), "DataFrame vazio após processar dados do EE."

        # Remove valores nulos
        df = df[df['Classe'].notnull()]
        
        if df.empty:
            return pd.DataFrame(columns=['Ano','Classe','Nome','Cor','Área (ha)']), "Todos os dados tinham classe nula."

        df['Classe'] = df['Classe'].astype(int)
        
        # Remove classe 27 (Não Observado)
        df = df[df['Classe'] != 27]
        
        if df.empty:
            return pd.DataFrame(columns=['Ano','Classe','Nome','Cor','Área (ha)']), "Todos os registros eram classe 27 (Não Observado). A ROI pode estar em área sem dados MapBiomas ou fora do Brasil."
        
        df['Área (ha)'] = pd.to_numeric(df['Área (ha)'], errors='coerce').fillna(0).round(2)
        df['Ano'] = df['Ano'].astype(int)

        df = df.merge(legenda_mapbiomas[['Classe','Nome','Cor']], on='Classe', how='left')
        df['Nome'] = df['Nome'].fillna(df['Classe'].apply(lambda x: f'Classe {x}'))
        df['Cor'] = df['Cor'].fillna('#888888')
        
        return df[['Ano','Classe','Nome','Cor','Área (ha)']], None

    except Exception as e:
        return pd.DataFrame(columns=['Ano','Classe','Nome','Cor','Área (ha)']), f"Erro ao calcular série temporal: {str(e)}"


# --- Layout da Aplicação Streamlit ---

st.set_page_config(layout="wide", page_title="MapBiomas LULC Temporal", initial_sidebar_state="expanded")

# CSS customizado para melhor visual
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1f77b4 0%, #2ca02c 100%);
        padding: 30px;
        border-radius: 10px;
        color: white;
        margin-bottom: 30px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        font-size: 2.5em;
        margin: 0;
        font-weight: 700;
    }
    .main-header p {
        font-size: 1.1em;
        margin: 10px 0 0 0;
        opacity: 0.95;
    }
    .feature-box {
        background: #f0f4f8;
        padding: 20px;
        border-radius: 8px;
        border-left: 4px solid #2ca02c;
        margin: 15px 0;
    }
    .feature-title {
        font-weight: 600;
        color: #1f77b4;
        font-size: 1.1em;
    }
</style>

<div class="main-header">
    <h1>🗺️ MapBiomas LULC Temporal</h1>
    <p>Análise Geotemporal de Uso e Cobertura da Terra - Coleção 9 (30m)</p>
</div>
""", unsafe_allow_html=True)

# Descrição e instruções com animação (expander)
with st.expander("📋 Sobre esta Aplicação", expanded=False):
    st.markdown("""
A plataforma **MapBiomas LULC Temporal** permite a análise de mudanças no uso e cobertura da terra no Brasil através dos dados da coleção 9 do MapBiomas.

**Funcionalidades principais:**
- 📊 **Análise de Ano Único**: Visualize a distribuição de classes de uso e cobertura em um ano específico
- 📈 **Série Histórica**: Acompanhe a evolução temporal de diferentes classes
- 💾 **Exportação de Dados**: Baixe resultados em formato Excel e GeoJSON

### 🚀 Como Começar

1. **Defina sua Área de Interesse (ROI)** na barra lateral:
   - Faça upload de um arquivo GeoJSON, Shapefile, KML ou ZIP
   - Ou desenhe diretamente no mapa de interação

2. **Configure o período de análise**:
   - Selecione um ano de referência ou dois anos para análise de transição

3. **Execute a análise** clicando em "Executar Análise/Visualização"

4. **Visualize os resultados** em gráficos interativos e exporte os dados
    """)

st.markdown("---")


# --- Sidebar: Configurações e Upload/Desenho ---
with st.sidebar:
    st.markdown("## ⚙️ Configurações de Análise")
    
    # 1. Coleção é fixa
    st.success(f"✨ **Coleção Ativa:** MapBiomas LULC Coleção 9 (30m)")
    
    st.markdown("---")
    
    # Reconectar GEE
    def _reconnect_gee():
        try:
            initialize_ee.clear()
        except Exception:
            pass
        inst = initialize_ee()
        if inst:
            st.success("GEE reconectado com sucesso.")
        else:
            st.error("Falha ao reconectar ao GEE. Verifique as credenciais.")

    if st.button("🔌 Reconectar ao GEE", use_container_width=True):
        _reconnect_gee()

    st.markdown("---")
    
    # 2. Definição da ROI (Upload ou Desenho)
    st.markdown("### 📍 Área de Interesse (ROI)")
    st.markdown("**Opção 1: Upload de Arquivo**")
    uploaded_file = st.file_uploader(
        "Selecione GeoJSON, SHP, KML ou ZIP", 
        type=["geojson", "shp", "dbf", "shx", "prj", "cpg", "kml", "zip"], 
        accept_multiple_files=True,
        key="file_uploader_sidebar",
        label_visibility="collapsed"
    )
    
    if uploaded_file and st.session_state["roi_source"] != "Upload":
        geojson_data, status_msg = read_and_convert_geojson_shp_kml(uploaded_file)
        if geojson_data:
            st.session_state["roi_geometry_data"] = geojson_data
            st.session_state["roi_source"] = "Upload"
            st.session_state["geemap_map_object"] = None 
            st.rerun() 
        else:
            st.sidebar.error(status_msg)

    # Status da ROI Salva
    if st.session_state["roi_geometry_data"]:
         st.sidebar.success(f"✅ ROI definida: **{st.session_state['roi_source']}**")
    else:
         st.sidebar.info("⚠️ Nenhuma ROI definida. Use upload ou desenhe no mapa.")
    
    # Botão para redefinir ROI (limpa desenhos e uploads anteriores)
    if st.button("🧹 Limpar Seleção de ROI", use_container_width=True):
        st.session_state["drawn_geojson"] = None
        st.session_state["geojson_roi"] = None
        st.session_state["roi_geometry_data"] = None
        st.session_state["stats_df"] = None
        st.session_state["roi_source"] = "Nenhuma"
        st.success("✅ ROI limpa. Defina uma nova área.")

    st.markdown("---")

    min_year = 1985
    available_years = list(range(min_year, 2024))
    
    # 3. Seleção de Ano(s)
    st.markdown("### 📅 Período de Análise")
    
    # Checkbox para Análise de Transição (MapBiomas é o único disponível)
    enable_transition = st.checkbox("🔄 Análise de Transição (Dois Anos)", 
                                    value=st.session_state["enable_transition"],
                                    help="Ative para comparar dois períodos distintos")
    st.session_state['enable_transition'] = enable_transition
    
    # --- Lógica de Segurança de Ano ---
    if st.session_state["ano_atual"] not in available_years:
        st.session_state["ano_atual"] = available_years[-1]
    if st.session_state["ano_inicial"] not in available_years:
        st.session_state["ano_inicial"] = available_years[0]
    
    
    if enable_transition:
        col_i, col_f = st.columns(2)
        with col_i:
            ano_inicial = st.selectbox(
                "📅 Ano Inicial:", available_years, 
                index=available_years.index(st.session_state["ano_inicial"]),
                key="ano_inicial_select"
            )
        with col_f:
            ano_final = st.selectbox(
                "📅 Ano Final:", available_years, 
                index=available_years.index(st.session_state["ano_atual"]),
                key="ano_final_select"
            )
        st.session_state["ano_inicial"] = ano_inicial
        st.session_state["ano_atual"] = ano_final
        if ano_inicial >= ano_final:
            st.error("O Ano Final deve ser maior que o Ano Inicial para análise de transição.")
            run_analysis = False 
        
    else:
        ano_novo = st.selectbox(
            "📅 Selecione o Ano de Referência:", available_years, 
            index=available_years.index(st.session_state["ano_atual"]),
            key="ano_unico_select"
        )
        st.session_state["ano_atual"] = ano_novo
        st.session_state["ano_inicial"] = st.session_state["ano_atual"] 

    st.sidebar.markdown("---")
    
    # 4. Botão de Análise
    st.markdown("### 🚀 Executar")
    run_analysis = st.button("▶️ Executar Análise/Visualização", use_container_width=True, type="primary")


# ====================================================
# DEFINIÇÃO E VISUALIZAÇÃO DA REGIÃO DE INTERESSE (ROI)
# ====================================================

roi = None 
geojson_data = st.session_state.get("roi_geometry_data")

if geojson_data:
    try:
        roi = geemap.geojson_to_ee(geojson_data)
        if roi.size().getInfo() == 0:
             raise ValueError("Geometria vazia")
    except Exception as e:
        st.session_state["roi_source"] = "Nenhuma"
        st.session_state["roi_geometry_data"] = None
        st.session_state["geemap_map_object"] = None
        st.error(f"Erro ao carregar ROI da sessão: {e}. Por favor, redefina a área.")

# Lógica de Desenho se não houver ROI
if roi is None:
    st.markdown("### 🎯 Opção 2: Desenhar Área no Mapa")
    st.info("Use as ferramentas de desenho à esquerda para selecionar sua área de interesse no mapa abaixo.")
    folium_map = folium.Map(location=[-14, -54], zoom_start=5)
    draw = folium.plugins.Draw(export=False)
    draw.add_to(folium_map)
    draw_result = st_folium(folium_map, height=600, width=1000, key="folium_draw_map")

    if draw_result and draw_result.get("all_drawings"):
        feature = draw_result["all_drawings"][0]
        if feature.get("geometry") and feature["geometry"].get("coordinates"):
            geojson_data = {"type": "FeatureCollection", "features": [feature]}
            st.session_state["roi_source"] = "Desenho"
            st.session_state["roi_geometry_data"] = geojson_data
            st.session_state["geemap_map_object"] = None
            st.sidebar.success("✅ ROI desenhada definida. Recarregando...")
            st.rerun()

# --- Inicialização e Renderização do Mapa GEEMAP ---

if roi is not None:
    st.markdown("---")
    st.markdown("### 🗺️ Mapa de Análise")
    st.info(f"📍 ROI Definida | 📅 Ano: **{st.session_state['ano_atual']}**")

    force_recreate = st.session_state.get("geemap_map_object") is None or st.session_state["roi_source"] != "Atual"
    
    if force_recreate:
        m = geemap.Map(center=[-14.5, -52], zoom=4, locate_control=True, draw_control=False)
        m.add_basemap("OpenStreetMap")
        m.centerObject(roi, zoom=10)
        st.session_state["geemap_map_object"] = m
        st.session_state["roi_source"] = "Atual"
    else:
        m = st.session_state["geemap_map_object"]

    base_year = st.session_state["ano_atual"]

    # =========================================================
    # REMOVE CAMADAS ANTIGAS DO MAPBIOMAS
    # =========================================================
    remove_layers_by_prefix(m, "MapBiomas")

    # =========================================================
    # ANÁLISE DE CAMADAS
    # =========================================================
    enable_transition = st.session_state.get('enable_transition', False)

    if enable_transition:
        ano_inicial = st.session_state.get('ano_inicial')
        st.info(f"🗺️ Mapa com 2 Camadas: {ano_inicial} e {base_year}")

        initial_image, initial_params, initial_layer_name = get_map_image(ano_inicial, roi=roi)
        if initial_image is not None:
            add_ee_layer_compat(m, initial_image, initial_params, initial_layer_name, False, 0.6)

        final_image, final_params, final_layer_name = get_map_image(base_year, roi=roi)
        if final_image is not None:
            add_ee_layer_compat(m, final_image, final_params, final_layer_name, True, 0.7)

    else:
        base_image, base_params, base_layer_name = get_map_image(base_year, roi=roi)
        if base_image is not None:
            add_ee_layer_compat(m, base_image, base_params, base_layer_name, True, 0.7)

    # =========================================================
    # ROI
    # =========================================================
    remove_layers_by_prefix(m, "🔴 ROI")

    try:
        add_ee_layer_compat(m, roi, {'color': 'FF0000', 'fillColor': '00000000'}, "🔴 ROI - Área de Interesse", True, 0.8)
    except Exception as e:
        st.warning(f"Não foi possível adicionar ROI ao mapa: {e}")

    # Controle de camadas
    try:
        if not st.session_state.get("layer_control_added", False):
            m.add_layer_control()
            st.session_state["layer_control_added"] = True
    except Exception:
        pass

    m.to_streamlit(height=700)

else:
    st.info("Utilize as opções na barra lateral ou desenhe no mapa acima para definir sua Área de Interesse.")

# --- Lógica de Análise Principal (Executada após o clique no botão) ---

if run_analysis and roi is not None:
    # Verifica se Earth Engine está operacional antes da análise
    try:
        _ = ee.Image(1).getInfo()
    except Exception:
        st.error("Earth Engine não está inicializado. Use '🔌 Reconectar ao GEE' e tente novamente.")
        st.stop()
    
    st.session_state["stats_df"] = None 
    st.session_state["transition_df"] = None 
    
    try:
        st.success(f"Iniciando processamento para ROI...")
        
        if st.session_state['enable_transition']:
            # ANÁLISE DE TRANSIÇÃO
            with st.spinner(f"Processando matriz de transição de {st.session_state['ano_inicial']} para {st.session_state['ano_atual']}..."):
                df_transition = process_transition_analysis(roi, st.session_state["ano_inicial"], st.session_state["ano_atual"])
                st.session_state["transition_df"] = df_transition
                if df_transition is not None and not df_transition.empty:
                    st.success("Cálculo de Matriz de Transição MapBiomas concluído.")
                else:
                    st.warning("Matriz de transição retornou vazia ou nula.")
                
        else:
            # ANÁLISE DE ANO ÚNICO
            with st.spinner(f"Processando dados MapBiomas para o ano {st.session_state['ano_atual']}..."):
                
                df_stats, roi_geojson_final_str, lulc_clipped = process_single_year_analysis(roi, st.session_state["ano_atual"])
                
                if df_stats is not None:
                    st.session_state["stats_df"] = df_stats 
                    st.session_state["geojson_roi"] = roi_geojson_final_str
                    st.session_state["lulc_clipped"] = lulc_clipped  # Salva para exportação GeoTIFF
                    st.success(f"Análise de Área MapBiomas do ano {st.session_state['ano_atual']} concluída!")

    except Exception as e:
        st.error(f"Erro ao executar a análise: {e}")
            
# --- Exibição dos Resultados (Gráficos e Exportação COM CORREÇÃO DE CORES) ---

st.markdown("---")


# 1. Resultados da Análise de Transição
if st.session_state["transition_df"] is not None and not st.session_state["transition_df"].empty:
    df_t = st.session_state["transition_df"]
    ano_i = st.session_state['ano_inicial']
    ano_f = st.session_state['ano_atual']

    # Remove transições envolvendo classe 27 (Não Observado) para não inflar permanência
    df_t_clean = df_t[(df_t['Classe Inicial'] != 27) & (df_t['Classe Final'] != 27)].copy()
    if df_t_clean.empty:
        st.warning("Matriz sem dados após remover 'Não Observado (27)'. Verifique se a ROI está em área mapeada.")
        st.stop()    

    pivot_df = df_t_clean.pivot_table(
        index='Nome Inicial', columns='Nome Final', values='Área (ha)', fill_value=0
    ).reset_index()

    # Série temporal empilhada por classe (período selecionado)
    st.subheader("Série Histórica de Área por Classe")
    y_start, y_end = sorted([ano_i, ano_f])
    years_series = list(range(y_start, y_end + 1))
    
    # Limpa cache se os parâmetros mudaram
    cache_key = f"series_{y_start}_{y_end}"
    if st.session_state.get('last_series_key') != cache_key:
        area_time_series.clear()
        st.session_state['last_series_key'] = cache_key
    
    # Gera hash da ROI E dos anos para invalidar cache quando qualquer um mudar
    roi_hash = str(hash(str(st.session_state.get('roi_geometry_data')) + str(years_series)))
    
    with st.spinner(f"Calculando série histórica para {len(years_series)} anos ({y_start}-{y_end})... Isso pode levar alguns segundos."):
        result = area_time_series(roi, years_series, roi_hash=roi_hash)
        
    # Verifica se retornou tupla (DataFrame, mensagem_erro) ou só DataFrame
    if isinstance(result, tuple):
        df_series, error_msg = result
    else:
        df_series = result
        error_msg = None
    
    if not df_series.empty:
        color_map_series = dict(zip(df_series['Nome'], df_series['Cor']))
        # Ajusta dtick baseado no range de anos
        year_range = y_end - y_start
        dtick = 1 if year_range <= 10 else (2 if year_range <= 20 else 5)
        
        fig_series = px.bar(
            df_series,
            x='Ano', y='Área (ha)', color='Nome',
            color_discrete_map=color_map_series,
            barmode='stack',
            title=f"Uso e Cobertura do Solo ({y_start}-{y_end}) - MapBiomas Col. 9",
            height=450
        )
        fig_series.update_traces(
            hovertemplate='<b>Ano %{x}</b><br>%{fullData.name}: %{y:,.2f} ha<extra></extra>'
        )
        fig_series.update_layout(
            xaxis_title='Ano',
            yaxis_title='Área (hectares)',
            xaxis={'dtick': dtick, 'tickangle': 0},
            yaxis={'tickformat': ',.0f'},
            showlegend=True,
            legend_title='Classe (cores MapBiomas)',
            legend=dict(orientation='v', yanchor='top', y=1, xanchor='left', x=1.02),
            hovermode='x unified'
        )
        st.plotly_chart(fig_series, use_container_width=True)

        # Exportação da série histórica em Excel (com legenda) - Formato pivoteado
        # Pivoteia para ter Anos como linhas e Classes como colunas
        df_series_pivot = df_series.pivot_table(
            index='Ano',
            columns='Nome',
            values='Área (ha)',
            fill_value=0
        ).reset_index()
        
        series_export = to_excel_multi({
            'serie_historica': df_series_pivot,
            'legenda': legenda_mapbiomas[['Classe','Nome','Cor']]
        })
        st.download_button(
            label="⬇️ Baixar Série Histórica Selecionada (.xlsx)",
            data=series_export,
            file_name=f'mapbiomas_serie_historica_{y_start}_{y_end}.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        if error_msg:
            st.warning(f"⚠️ Série histórica vazia: {error_msg}")
        else:
            st.info("Série histórica vazia para esta ROI (fora da área mapeada ou sem dados em alguns anos).")
        
        st.info("💡 **Sugestões:**\n"
                "- Verifique se sua ROI está dentro do território brasileiro\n"
                "- Tente uma área menor ou diferente\n"
                "- Verifique se os anos selecionados têm dados disponíveis")

    # Gráfico das Maiores Transições (Excluindo Permanência)
    df_mudanca = df_t_clean[df_t_clean['Classe Inicial'] != df_t_clean['Classe Final']].sort_values('Área (ha)', ascending=False).head(10)
    
    if not df_mudanca.empty:
        st.subheader("Top 10 Maiores Mudanças (Transições)")
        df_mudanca['Transição'] = df_mudanca['Nome Inicial'] + ' -> ' + df_mudanca['Nome Final']
        
        fig_trans = px.bar(df_mudanca, x='Transição', y='Área (ha)', color='Área (ha)',
                           title=f"Maiores Transições de {ano_i} para {ano_f}",
                           height=500)
        st.plotly_chart(fig_trans, use_container_width=True)
    
    # Exportação da Matriz Completa
    export_transition = to_excel_multi({
        'transicoes': df_t_clean,
        'pivot': pivot_df,
        'legenda': legenda_mapbiomas[['Classe','Nome','Cor']]
    })


# 2. Resultados da Análise de Ano Único (se não for transição)
elif st.session_state["stats_df"] is not None:
    df = st.session_state["stats_df"]
    # 1. Filtra classes com área > 0 para limpar a legenda
    df_clean = df[df["Área (ha)"] > 0].copy() 
    ano = st.session_state['ano_atual']
    
    st.header(f"📈 Resultados da Análise de Área - MapBiomas ({ano})")
    
    col_bar, col_pie = st.columns(2)

    # Cria o mapeamento de cores baseado nos nomes das classes
    color_map_nome = dict(zip(df_clean["Nome"].tolist(), df_clean["Cor"].tolist()))
    
    with col_bar:
        st.markdown("### 📊 Gráfico de Barras - Área por Classe")
        # Usa a coluna 'Nome' no parâmetro 'color' para mostrar os nomes na legenda
        fig_bar = px.bar(df_clean, x="Nome", y="Área (ha)", color="Nome", 
                         color_discrete_map=color_map_nome,
                         title=f"Distribuição de Uso e Cobertura ({ano})")
                         
        # Ajustes de Layout e Legenda para Barras
        fig_bar.update_traces(hovertemplate='<b>%{x}</b><br>Área: %{y:,.2f} ha<extra></extra>')
        fig_bar.update_layout(
            xaxis={'categoryorder': 'total descending'},
            showlegend=True, 
            legend_title="Usos e Coberturas"
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        

    with col_pie:
        st.markdown("### 🥧 Gráfico de Pizza - Área por Classe")
        # Usa a coluna 'Nome' para mostrar os nomes na legenda
        fig_pie = px.pie(df_clean, values="Área (ha)", names="Nome",
                         color="Nome", 
                         color_discrete_map=color_map_nome,
                         title=f"Proporção de Uso e Cobertura ({ano})")
                         
        # Ajusta o template de hover para mostrar informações detalhadas
        fig_pie.update_traces(
            hovertemplate='<b>%{label}</b><br>Área: %{value:,.2f} ha<br>Proporção: %{percent}<extra></extra>',
            textposition='inside',
            textinfo='percent+label'
        )
        
        # 4. Ajustes de Layout e Legenda para Pizza
        fig_pie.update_layout(
            showlegend=True, 
            legend_title="Usos e Coberturas",
            hovermode='closest',
            font=dict(size=11)
        )
        
        st.plotly_chart(fig_pie, use_container_width=True)
        
    
    st.markdown("---")
    st.header("📥 Exportação de Dados")
    
    col_export_excel, col_export_geojson, col_export_geotiff = st.columns(3)
    
    # 1. Exportação para Excel
    with col_export_excel:
        st.markdown("#### Exportar Tabela de Estatísticas (.xlsx)")
        excel_data = to_excel_multi({
            'area_por_classe': df_clean,
            'legenda': legenda_mapbiomas[['Classe','Nome','Cor']]
        })
        st.download_button(
            label="⬇️ Baixar como Excel",
            data=excel_data,
            file_name=f'mapbiomas_area_stats_{ano}.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            use_container_width=True
        )

    # 2. Exportação do GeoJSON da ROI
    with col_export_geojson:
        st.markdown("#### Exportar Geometria da ROI (.geojson)")
        if st.session_state["geojson_roi"]:
            st.download_button(
                label="⬇️ Baixar ROI como GeoJSON",
                data=st.session_state["geojson_roi"],
                file_name='area_de_interesse_roi.geojson',
                mime='application/json',
                use_container_width=True
            )
        else:
            st.info("Nenhuma geometria válida disponível para exportação.")
    
    # 3. Exportação como GeoTIFF
    with col_export_geotiff:
        st.markdown("#### Exportar Camada MapBiomas (.tiff)")
        if st.button("🌍 Gerar GeoTIFF", use_container_width=True):
            try:
                with st.spinner("⏳ Gerando GeoTIFF em resolução 30m..."):
                    # Recupera imagem recortada da sessão
                    export_image = st.session_state.get("lulc_clipped")
                    if export_image is None:
                        st.error("Imagem não disponível. Execute a análise primeiro.")
                    else:
                        # Mascara valores sem dados
                        export_image = export_image.unmask(27)
                        
                        # Calcula bounds da ROI
                        roi_bounds = roi.geometry().bounds()
                        
                        download_url = export_image.getDownloadUrl({
                            'scale': 30,
                            'crs': 'EPSG:4326',
                            'fileFormat': 'GeoTIFF',
                            'region': roi_bounds.getInfo()
                        })
                        
                        st.success("✅ GeoTIFF gerado com sucesso!")
                        st.markdown(f"[📥 Clique para baixar]({download_url})")
                        st.caption("💡 Dados georeferenciados (EPSG:4326) | Resolução: 30m")
                
            except Exception as e:
                st.error(f"⚠️ Erro ao gerar GeoTIFF: {str(e)}")
                st.info("💡 **Dica:** Se a ROI for muito grande, tente reduzi-la ou use a exportação em Excel como alternativa.")

# --- Próximo Passo Sugerido ---
st.markdown("---")

if not st.session_state.get('enable_transition'):
     st.info("💡 **Próximo Passo:** Gostaria de executar a Análise de Transição? Ative a opção **'Habilitar Análise de Transição (Dois Anos)'** no sidebar e clique em 'Executar Análise/Visualização'.")
elif st.session_state.get('enable_transition'):
     st.info("💡 **Próximo Passo:** Para recalcular, altere o ano inicial ou final no sidebar e clique em 'Executar Análise/Visualização'.")


# --- Rodapé com Branding Pessoal ---
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 30px 20px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 10px; margin-top: 40px;">
    <p style="font-size: 14px; color: #555; margin: 10px 0;">
        <strong>Desenvolvido por:</strong>
    </p>
    <h3 style="margin: 10px 0; color: #1f77b4;">👨‍💻 Ruan Almeida</h3>
    <p style="font-size: 13px; color: #666; margin: 15px 0;">
        <a href="https://www.linkedin.com/in/ruan-almeida-8b8136295/" target="_blank" style="text-decoration: none; color: #0A66C2; font-weight: 600; margin: 0 15px;">
            🔗 LinkedIn
        </a>
        <a href="https://www.instagram.com/ruan_almeida_martins/" target="_blank" style="text-decoration: none; color: #E4405F; font-weight: 600; margin: 0 15px;">
            📷 Instagram
        </a>
    </p>
    <p style="font-size: 12px; color: #999; margin-top: 15px;">
        MapBiomas LULC Temporal Analysis Platform
    </p>
</div>
""", unsafe_allow_html=True)
