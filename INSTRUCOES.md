# MapBiomas LULC Temporal - Estrutura do Repositório

## 📁 Pasta Pronta para GitHub

Esta pasta contém todos os arquivos necessários para publicar no GitHub e Streamlit Cloud.

### 📋 Arquivos Inclusos:

- **main.py** - Aplicação principal Streamlit
- **requirements.txt** - Dependências Python
- **packages.txt** - Dependências do sistema
- **README.md** - Documentação completa
- **.gitignore** - Arquivos a ignorar no Git
- **.streamlit/config.toml** - Configurações Streamlit

### 🚀 Como Publicar no GitHub:

#### **Opção 1: GitHub Desktop (Recomendado)**

1. Abra **GitHub Desktop**
2. **File** → **Add Local Repository**
3. Selecione esta pasta: `mapbiomas-lulc-temporal`
4. Clique em **Publish repository**
5. Nome: `mapbiomas-lulc-temporal`
6. Descrição: `Análise Geotemporal de Uso e Cobertura da Terra`
7. Deixe como **Public**

#### **Opção 2: Linha de Comando**

```powershell
cd "D:\Code\Projeto 1 - GEE_Streamlit\github_repo\mapbiomas-lulc-temporal"
git init
git add .
git commit -m "Initial commit: MapBiomas LULC Temporal App"
git remote add origin https://github.com/SEU-USUARIO/mapbiomas-lulc-temporal.git
git branch -M main
git push -u origin main
```

### ☁️ Deploy no Streamlit Cloud

Após publicar no GitHub:

1. Vá em [share.streamlit.io](https://share.streamlit.io)
2. Clique em **New app**
3. Selecione:
   - Repository: `SEU-USUARIO/mapbiomas-lulc-temporal`
   - Branch: `main`
   - Main file path: `main.py`
4. Clique em **Deploy**
5. Na aba **Settings**, vá em **Secrets** e adicione:

```toml
[google_earth_engine]
service_account_b64 = "SEU_JSON_CONVERTIDO_EM_BASE64"
```

### 🔐 Converter JSON para Base64

Execute este código Python:

```python
import base64

with open('SEU_JSON_AQUI.json', 'rb') as f:
    encoded = base64.b64encode(f.read()).decode()
    print(encoded)
```

Cole o resultado no campo `service_account_b64` do Streamlit Secrets.

### ✅ Checklist Antes de Publicar

- [ ] JSON do Google Earth Engine convertido em Base64
- [ ] Repositório criado no GitHub
- [ ] Arquivos no GitHub (sem `.json` sensíveis)
- [ ] Secrets configurados no Streamlit Cloud
- [ ] Deploy realizado

---

**Pronto para compartilhar! 🎉**
