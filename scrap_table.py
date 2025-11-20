import requests
from bs4 import BeautifulSoup
import boto3
import uuid
import json

def lambda_handler(event, context):
    # URL de la página de sismos reportados del IGP
    url = "https://ultimosismo.igp.gob.pe/ultimo-sismo/sismos-reportados"

    try:
        # Realizar la solicitud HTTP a la página web
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return {
                'statusCode': response.status_code,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Error al acceder a la página web del IGP'})
            }

        # Parsear el contenido HTML de la página web
        soup = BeautifulSoup(response.content, 'html.parser')

        # Encontrar la tabla de sismos en el HTML
        table = soup.find('table', class_='table')
        if not table:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'No se encontró la tabla de sismos en la página web'})
            }

        # Extraer los encabezados de la tabla
        headers_row = table.find('thead')
        if headers_row:
            headers = [header.text.strip() for header in headers_row.find_all('th')]
        else:
            headers = []

        # Extraer las filas de la tabla (solo los primeros 10 sismos)
        sismos = []
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')[:10]  # Limitar a los últimos 10 sismos
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) > 0:
                    sismo = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            sismo[headers[i]] = cell.text.strip()
                        else:
                            sismo[f'Campo_{i}'] = cell.text.strip()
                    sismos.append(sismo)

        if not sismos:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'No se encontraron sismos en la tabla'})
            }

        # Guardar los datos en DynamoDB
        dynamodb = boto3.resource('dynamodb')
        table_db = dynamodb.Table('TablaSismosIGP')

        # Eliminar todos los elementos de la tabla antes de agregar los nuevos
        scan = table_db.scan()
        with table_db.batch_writer() as batch:
            for item in scan['Items']:
                batch.delete_item(
                    Key={
                        'id': item['id']
                    }
                )

        # Insertar los nuevos datos de sismos
        for index, sismo in enumerate(sismos, start=1):
            sismo['#'] = index
            sismo['id'] = str(uuid.uuid4())  # Generar un ID único para cada sismo
            table_db.put_item(Item=sismo)

        # Retornar el resultado como JSON
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': f'Se guardaron {len(sismos)} sismos en DynamoDB',
                'sismos': sismos
            }, ensure_ascii=False)
        }

    except requests.exceptions.RequestException as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Error en la solicitud HTTP: {str(e)}'})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': f'Error inesperado: {str(e)}'})
        }