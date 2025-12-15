# 🗺️ MapBiomas LULC Temporal - Análise Geotemporal

Aplicação Streamlit para análise de mudanças no uso e cobertura da terra no Brasil usando dados do MapBiomas Coleção 9.

## 🚀 Funcionalidades

- 📊 **Análise de Ano Único**: Visualize distribuição de classes de uso e cobertura em um ano específico
- 🔄 **Análise de Transição**: Identifique mudanças entre dois períodos (matriz de transição)
- 📈 **Série Histórica**: Acompanhe evolução temporal de diferentes classes (1985-2023)
- 🗺️ **Mapa Interativo**: Visualize camadas MapBiomas com controle de transparência
- 💾 **Exportação**: Excel, GeoJSON e GeoTIFF

## 📋 Pré-requisitos

- Python 3.9+
- Conta Google Earth Engine (Service Account)
- Credenciais JSON do Google Earth Engine

## 🔧 Instalação Local

```bash
# Clone o repositório
git clone <seu-repositorio>
cd web

# Instale as dependências
pip install -r requirements.txt

# Configure as credenciais do Google Earth Engine
# Coloque seu arquivo service_account.json na pasta raiz
# OU configure via Streamlit Secrets (recomendado para produção)
```

## ⚙️ Configuração do Google Earth Engine

### Opção 1: Arquivo Local (desenvolvimento)
Coloque o arquivo `service_account.json` na pasta `web/`

### Opção 2: Streamlit Secrets (produção/cloud)

Crie `.streamlit/secrets.toml`:

```toml
[google_earth_engine]
service_account_b64 = "SEU_JSON_EM_BASE64_AQUI"
```

Para converter seu JSON para Base64:
```python
import base64
import json

with open('service_account.json', 'rb') as f:
    encoded = base64.b64encode(f.read()).decode()
    print(encoded)
```

## 🚀 Executar Localmente

```bash
streamlit run main.py
```

## ☁️ Deploy no Streamlit Cloud

1. **Push do código para GitHub** (sem o arquivo `service_account.json`)

2. **No Streamlit Cloud**:
   - Vá em [share.streamlit.io](https://share.streamlit.io)
   - Conecte seu repositório
   - Em **Advanced settings > Secrets**, adicione:
   
   ```toml
   [google_earth_engine]
   service_account_b64 = "SEU_JSON_CONVERTIDO_EM_BASE64"
   ```

3. **Deploy!** 🎉

## 📦 Estrutura de Arquivos

```
web/
├── main.py                 # Aplicação principal
├── requirements.txt        # Dependências Python
├── packages.txt           # Dependências do sistema (GDAL)
├── palette_biome.py       # Paletas de cores (opcional)
├── .streamlit/
│   └── config.toml        # Configurações do Streamlit
├── .gitignore            # Arquivos ignorados pelo Git
└── README.md             # Este arquivo
```

## 🗂️ Como Usar

1. **Defina a ROI** (Região de Interesse):
   - Upload de arquivo: GeoJSON, Shapefile, KML ou ZIP
   - Desenho direto no mapa interativo

2. **Configure a análise**:
   - Selecione um ano único OU
   - Ative análise de transição (dois anos)

3. **Execute a análise**

4. **Visualize resultados**:
   - Gráficos interativos (barras e pizza)
   - Mapa com camadas MapBiomas
   - Série histórica temporal

5. **Exporte dados**:
   - Excel (.xlsx) com estatísticas
   - GeoJSON com geometria da ROI
   - GeoTIFF georeferenciado

## 🛠️ Tecnologias

- **Streamlit**: Framework web
- **Google Earth Engine**: Processamento geoespacial em nuvem
- **GeoPandas**: Manipulação de dados vetoriais
- **Plotly**: Gráficos interativos
- **Folium**: Mapas interativos

## 📊 Dados

- **Fonte**: MapBiomas Brasil - Coleção 9
- **Resolução**: 30 metros
- **Período**: 1985-2023
- **Classificação**: 69 classes de uso e cobertura da terra

## 🔒 Segurança

⚠️ **IMPORTANTE**: Nunca faça commit do arquivo `service_account.json` no Git!

- Use `.gitignore` para proteger credenciais
- Use Streamlit Secrets para produção
- Mantenha suas credenciais em Base64 nos secrets

## 📝 Licença

Este projeto usa dados do MapBiomas (CC BY-SA 4.0)

## 🤝 Contribuições

Contribuições são bem-vindas! Abra uma issue ou pull request.

## 📧 Contato

Para dúvidas ou sugestões, abra uma issue no repositório.

---

**Desenvolvido com ❤️ usando Streamlit e Google Earth Engine**
