from google.oauth2 import service_account
from googleapiclient.discovery import build
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime

# Configuración de autenticación y conexión con GSC
CREDENTIALS_FILE = '/Users/ivangarcia/Desktop/pruebascriptgsc-7766cf0aaf44.json'
SITE_URL = 'sc-domain:modelosyformularios.es'

# Autenticación de la cuenta de GSC
credentials = service_account.Credentials.from_service_account_file(
    CREDENTIALS_FILE,
    scopes=['https://www.googleapis.com/auth/webmasters']
)

# Construcción del cliente de la API de Google Search Console
service = build('searchconsole', 'v1', credentials=credentials)

# Definir el rango de fechas y la URL a procesar
end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=28)
target_url = 'https://modelosyformularios.es/modelos/modelo-002/'

# Configurar la solicitud a la API de GSC
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
            'expression': target_url
        }]
    }]
}

# Consultar los datos de rendimiento para la URL especificada
response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()

# Extraer las palabras clave (queries), impresiones y clics de la respuesta de GSC
keywords_data = []
if 'rows' in response:
    for row in response['rows']:
        keywords_data.append({
            'keyword': row['keys'][0],
            'clicks': row['clicks'],
            'impressions': row['impressions']
        })

# Obtener el contenido de una URL
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

# Verificar la presencia de palabras clave en el contenido
def check_keywords_in_content(content, keywords_data):
    if content is None:
        return {}
    
    content_lower = content.lower()
    keyword_planteada = {data['keyword']: {'planteada': False, 'clicks': data['clicks'], 'impressions': data['impressions']} for data in keywords_data}
    for data in keywords_data:
        keyword = data['keyword']
        if keyword.lower() in content_lower:
            keyword_planteada[keyword]['planteada'] = True
            
    return keyword_planteada

# Extraer y analizar el contenido relevante de una página
def parse_content(url, content):
    soup = BeautifulSoup(content, 'html.parser')
    relevant_text = ""
    target_div = soup.find('div', class_='entry-content clear')
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

# Procesar la URL y guardar los resultados
def process_url(url, keywords_data):
    content = fetch_url_content(url)
    if content:
        relevant_text = parse_content(url, content)
        return check_keywords_in_content(relevant_text, keywords_data)
    else:
        return None

# Main execution
if __name__ == "__main__":
    result = process_url(target_url, keywords_data)
    
    # Preparar los datos para la exportación
    export_data = []
    if result:
        for keyword, data in result.items():
            export_data.append({
                'URL': target_url,
                'Keyword': keyword,
                'Planteada': data['planteada'],
                'Clicks': data['clicks'],
                'Impressions': data['impressions']
            })
    
    # Convertir la lista de diccionarios a un DataFrame
    results_df = pd.DataFrame(export_data)
    
    # Exportar a CSV
    output_file = '/Users/ivangarcia/Downloads/results.xlsx'
    results_df.to_excel(output_file, index=False)
    print(f"Results have been exported to {output_file}")
    
    # Leer el archivo Excel y realizar cálculos
    df = pd.read_excel(output_file)
    
    # Cálculos de métricas
    summary_df = df.groupby('URL').agg({
        'Planteada': ['sum', lambda x: (~x).sum()],
        'Impressions': lambda x: x[df['Planteada'] == False].sum(),
        'Clicks': lambda x: x[df['Planteada'] == False].sum()
    }).reset_index()

    summary_df.columns = ['URL', 'Count_True_KW', 'Count_False_KW', 'Sum_Impressions_False_KW', 'Sum_Clicks_False_KW']
    
    # Guardar el resumen en una NUEVA HOJA 'SUMMARY' del archivo Excel
    with pd.ExcelWriter(output_file, mode='a', engine='openpyxl', if_sheet_exists='new') as writer:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    print(f"Summary has been added to a new sheet in {output_file}")
