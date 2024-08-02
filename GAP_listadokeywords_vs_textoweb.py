from google.oauth2 import service_account
from googleapiclient.discovery import build
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Configuración de autenticación y conexión con GSC
CREDENTIALS_FILE = '/Users/ivangarcia/Desktop/pruebascriptgsc-7766cf0aaf44.json'
SHEET_CREDENTIALS_FILE = '/Users/ivangarcia/Desktop/pruebascriptgsc-a2defdcf30d2.json'

# URL de tu propiedad en Google Search Console
SITE_URL = 'sc-domain:modelosyformularios.es'

# Autenticación de la cuenta de GSC
credentials = service_account.Credentials.from_service_account_file(
    CREDENTIALS_FILE,
    scopes=['https://www.googleapis.com/auth/webmasters']
)

# Construcción del cliente de la API de Google Search Console
service = build('searchconsole', 'v1', credentials=credentials)

# Especificar el rango de fechas para la consulta (últimos 28 días en este ejemplo)
end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=28)

# Consultar los datos de rendimiento para la URL especificada
request = {
    'startDate': start_date.isoformat(),
    'endDate': end_date.isoformat(),
    'dimensions': ['query'],
    'rowLimit': 1000,
    'dimensionFilterGroups': [{
        'groupType': 'and',
        'filters': [{
            'dimension': 'page',
            'operator': 'contains',
            'expression': 'https://modelosyformularios.es/modelos/modelo-002/'
        }]
    }]
}

response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()

# Extraer las palabras clave (queries) de la respuesta de GSC
keywords = []
if 'rows' in response:
    for row in response['rows']:
        keywords.append(row['keys'][0])

# Función para obtener el contenido de una URL
def fetch_url_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching the URL: {e}")
        return None

# Función para verificar la presencia de palabras clave en el contenido
def check_keywords_in_content(content, keywords):
    if content is None:
        return {}
    
    content_lower = content.lower()
    keyword_planteada = {keyword: False for keyword in keywords}
    for keyword in keywords:
        if keyword.lower() in content_lower:
            keyword_planteada[keyword] = True
            
    return keyword_planteada

# Función para extraer y analizar el contenido relevante de una página
def parse_content(url, content):
    soup = BeautifulSoup(content, 'html.parser')
    relevant_text = ""
    target_div = soup.find('div', class_='c-description-block__container container-fluid u-max-width')
    if target_div:
        relevant_text += target_div.get_text(separator=' ')
    else:
        print(f"The specified div with the class was not found in the URL: {url}")
    
    h1_tag = soup.find('h1')
    if h1_tag:
        relevant_text += " " + h1_tag.get_text(separator=' ')
    else:
        print(f"The h1 tag was not found in the URL: {url}")
    
    return relevant_text

# Función para procesar una URL específica y hacer match de palabras clave con su contenido
def process_url(url, keywords):
    content = fetch_url_content(url)
    if content:
        relevant_text = parse_content(url, content)
        return check_keywords_in_content(relevant_text, keywords)
    else:
        return None

# Procesar la URL con las palabras clave obtenidas de GSC
if __name__ == "__main__":
    target_url = 'https://modelosyformularios.es/modelos/modelo-002/'  # Cambia esto según tus necesidades
    result = process_url(target_url, keywords)
    
    # Preparar los datos para la exportación
    export_data = []
    if result:
        for keyword, planteada in result.items():
            export_data.append({
                'URL': target_url,
                'Keyword': keyword,
                'Planteada': planteada
            })
    
    # Convertir la lista de diccionarios a un DataFrame
    results_df = pd.DataFrame(export_data)
    
    # Exportar a CSV
    output_file = '/Users/ivangarcia/Downloads/results.csv'
    results_df.to_csv(output_file, index=False)
    print(f"Results have been exported to {output_file}")
