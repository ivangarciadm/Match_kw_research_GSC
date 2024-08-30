from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Función para eliminar caracteres acentuados
def remove_accents(text):
    replacements = {
        'á': 'a',
        'é': 'e',
        'í': 'i',
        'ó': 'o',
        'ú': 'u',
        'ü': 'u',
        'ñ': 'n'
    }
    for accented_char, normal_char in replacements.items():
        text = text.replace(accented_char, normal_char)
    return text

# Configuración de autenticación y conexión con GSC
CREDENTIALS_FILE = '/Users/ivan/Desktop/pruebascriptgsc-7766cf0aaf44.json'
SITE_URL = 'sc-domain:modelosyformularios.es'

# Autenticación de la cuenta de GSC
credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
service = build('searchconsole', 'v1', credentials=credentials)

# Fechas de consulta
end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=28)

# Función para consultar datos de GSC
def query_gsc(url):
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
                'expression': url
            }]
        }]
    }
    response = service.searchanalytics().query(siteUrl=SITE_URL, body=request).execute()
    return response

# Extraer las palabras clave (queries), impresiones y clics de la respuesta de GSC
def extract_keywords(response):
    keywords_data = []
    if 'rows' in response:
        for row in response['rows']:
            keywords_data.append({
                'keyword': row['keys'][0],
                'clicks': row['clicks'],
                'impressions': row['impressions']
            })
    return keywords_data

# Obtener el contenido de una URL
def fetch_url_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching the URL {url}: {e}")
        return None

# Verificar la presencia de palabras clave en el contenido
def check_keywords_in_content(content, keywords_data):
    if content is None:
        return {}

    content_normalized = remove_accents(content.lower())
    keyword_planteada = {remove_accents(data['keyword'].lower()): {'planteada': False, 'clicks': data['clicks'], 'impressions': data['impressions']} for data in keywords_data}

    for data in keywords_data:
        keyword = remove_accents(data['keyword'].lower())
        if keyword in content_normalized:
            keyword_planteada[keyword]['planteada'] = True

    return keyword_planteada

# Procesar el contenido de una URL
def process_url(url, keywords_data):
    content = fetch_url_content(url)
    if content:
        parsed_content = parse_content(url, content)
        keyword_summary = check_keywords_in_content(parsed_content, keywords_data)
        return keyword_summary
    else:
        return None

# Parsear el contenido de la página
def parse_content(url, content):
    soup = BeautifulSoup(content, 'html.parser')
    relevant_text = ""
    target_div = soup.find('div', class_='entry-content clear')
    if target_div:
        relevant_text += target_div.get_text(separator=' ')
    return relevant_text

# Procesar múltiples URLs con las palabras clave obtenidas de GSC
if __name__ == "__main__":
    # Obtener URLs desde el input del usuario
    urls_input = input("Introduce las URLs separadas por comas (máximo 30 URLs): ")
    urls = [url.strip() for url in urls_input.split(',')]

    # Validación de URLs introducidas
    if not urls or len(urls[0]) == 0:
        raise ValueError("Error: Debes introducir al menos una URL.")

    if len(urls) > 30:
        raise ValueError("Error: Se permiten un máximo de 30 URLs.")

    all_summaries = []
    output_file = '/Users/ivan/Desktop/results.xlsx'

    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        for url in urls:
            try:
                response = query_gsc(url)
            except Exception as e:
                print(f"Error al consultar GSC para {url}: {e}")
                continue  # Saltar a la siguiente URL si hay un error

            keywords_data = extract_keywords(response)
            result = process_url(url, keywords_data)

            if result:
                export_data = []
                for keyword, data in result.items():
                    export_data.append({
                        'URL': url,
                        'Keyword': keyword,
                        'Planteada': data['planteada'],
                        'Clicks': data['clicks'],
                        'Impressions': data['impressions']
                    })

                # Convertir la lista de diccionarios a un DataFrame
                results_df = pd.DataFrame(export_data)

                # Crear un nombre de hoja descriptivo basado en la URL
                sheet_name = f"URL_{urls.index(url) + 1}_{url.split('//')[1].split('/')[0][:20]}"  # Usar parte del dominio
                results_df.to_excel(writer, sheet_name=sheet_name, index=False)

                # Calculos de métricas para la hoja Summary
                summary = results_df.groupby('URL').apply(lambda x: pd.Series({
                    'Keywords no presentes': (x['Planteada'] == False).sum(),
                    'Impressions no presentes': x.loc[x['Planteada'] == False, 'Impressions'].sum(),
                    'Clicks no presentes': x.loc[x['Planteada'] == False, 'Clicks'].sum(),
                    'Keywords presentes': (x['Planteada'] == True).sum(),
                    'Impressions presentes': x.loc[x['Planteada'] == True, 'Impressions'].sum(),
                    'Clicks presentes': x.loc[x['Planteada'] == True, 'Clicks'].sum()
                })).reset_index()

                all_summaries.append(summary)

        # Crear y guardar la hoja de resumen 'Summary'
        summary_df = pd.concat(all_summaries, ignore_index=True)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
