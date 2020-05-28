"""Cloud Function that accepts a POST request"""
from google.cloud import storage
from google.cloud import error_reporting
import requests
import random
import json
import os

err_client = error_reporting.Client()
storage_client = storage.Client()

# Request headers template
HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9,nl;q=0.8',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Host': '',
    'Referer': '',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': ''
}

# 25 randomly generated user agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2225.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2226.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1650.16 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.137 Safari/4E423F',
    'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.3319.102 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2226.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36',
    'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; Trident/5.0)',
    'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.2309.372 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1667.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2225.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/29.0.1547.62 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36',
    'Mozilla/5.0 (X11; Linux i686; rv:64.0) Gecko/20100101 Firefox/64.0',
    'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1500.55 Safari/537.36',
    'Mozilla/5.0 (compatible; MSIE 8.0; Windows NT 5.2; Trident/4.0; Media Center PC 4.0; SLCC1; .NET CLR 3.0.04320)',
    'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML like Gecko) Chrome/44.0.2403.155 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:39.0) Gecko/20100101 Firefox/75.0',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1'
]


def get_headers(url) -> dict:
    """
    Copy HEADERS template, update values for `User-Agent`, `Host`, `Referer`, return formatted headers

    :type url: str
    :param url: The URL which to extract headers `Host` and `Referer` from.

    :rtype: dict
    :returns: The updated HEADERS
    """
    headers = HEADERS.copy()

    # Select a random user agent
    user_agent = USER_AGENTS[random.randint(0, len(USER_AGENTS) - 1)]

    # Extract the host
    host = url.split('/')[2]

    # Set the referrer to initial search page
    referrer = ''.join(['https://', host, '/d/apts-housing-for-rent/search/apa'])

    headers.update({
        'Host': host,
        'Referer': referrer,
        'User-Agent': user_agent,
    })
    return headers


def get_html(url: str) -> str:
    """
    Make the GET request, return the response text. Report any errors to Google Cloud Error reporting.

    :type url: str
    :param url: The URL to make the GET request to

    :rtype: str
    :returns: requests.Response.text
    """
    html_str = ''
    res = None
    err = None

    headers = get_headers(url)

    try:
        res = requests.get(url=url, headers=headers)
        res.raise_for_status()
        html_str = res.text
    except requests.exceptions.ConnectionError as connection_err:
        err = connection_err
    except requests.exceptions.HTTPError as http_err:
        err = http_err
    except requests.exceptions.RequestException as broad_err:
        err = broad_err
    finally:
        if err:
            status_code = res.status_code if res else None
            request_context = error_reporting.HTTPContext(
                method='GET', url=url, user_agent=headers['User-Agent'],
                referrer=headers['Referer'], response_status_code=status_code)
            err_client.report(message=str(err), http_context=request_context)

    return html_str


def upload_to_google_cloud_storage(request_json) -> bool:
    """
    Upload the object to Google Cloud Storage

    :type request_json: dict
    :param request_json:

    :rtype: bool
    :return: True on successful upload, False otherwise
    """
    upload_success = False
    try:
        bucket = storage_client.get_bucket(os.environ['GCS_BUCKET'])
        blob = bucket.blob(request_json['data_id'] + '.txt')
        blob.upload_from_string(json.dump(request_json))
        upload_success = True
    except Exception as e:
        err_client.report(message=str(e))

    return upload_success


def handler(request) -> tuple:
    """
    Main handler for Cloud Function. Responds to HTTP POST requests.

    :type request: :class:`flask.Request`
    :param request: HTTP Request object

    :rtype: tuple(dict, int)
    :returns: the data object and a response status code
    """
    request_json = request.get_json(silent=True)

    # Method not allowed
    if request.method != 'POST':
        return {'message': 'Only POST requests permitted.'}, 405

    # Missing required data
    if not request_json or 'href' not in request_json:
        return {'message': 'Missing required `href` in request.'}, 400

    html_text = get_html(request_json['href'])
    request_json.update({'html_text': html_text})

    uploaded = upload_to_google_cloud_storage(request_json)

    # successfully uploaded to GCS
    if not uploaded:
        return request_json, 200

    return request_json, 201

