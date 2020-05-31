"""Cloud Function that accepts a POST request """
from google.cloud import storage, error_reporting
from user_agents import USER_AGENTS
from templates import HEADERS
import requests
import random
import json
import os

err_client = error_reporting.Client()
storage_client = storage.Client()


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

    headers = get_headers(url)

    try:
        res = requests.get(url=url, headers=headers, timeout=1, allow_redirects=False)
        res.raise_for_status()  # Raise an exception for error codes (4xx or 5xx)
        html_str = res.text
    except requests.exceptions.RequestException as err:
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
    :return: True on successful upload, otherwise False
    """
    upload_success = False
    try:
        bucket = storage_client.get_bucket(os.environ['GCS_BUCKET'])
        blob = bucket.blob(str(request_json['data_id']) + '.txt')
        blob.upload_from_string(json.dumps(request_json))
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
        return json.dumps({'message': 'Only POST requests permitted.'}), 405

    # Missing required data
    if not request_json or 'href' not in request_json:
        return json.dumps({'message': 'Missing required `href` in request.'}), 400

    html_text = get_html(request_json['href'])

    # GET request failed
    if html_text == '':
        request_json.update({'message': 'GET request failed. See error reporting console for details.'})
        return json.dumps(request_json), 200

    request_json.update({'html': html_text})
    uploaded = upload_to_google_cloud_storage(request_json)

    # unsuccessful upload to Google Cloud Storage
    if not uploaded:
        request_json.update(
            {'message': 'Upload to Google Cloud Storage failed. See error reporting console for details.'})
        return json.dumps(request_json), 200

    return json.dumps(request_json), 201

