from unittest.mock import Mock, patch
import unittest
import main
import responses
import requests


class TestCloudFunction(unittest.TestCase):
    def setUp(self):
        self.TEST_CLOUD_FN_ENDPOINT = 'https://cloud-function-location-project-name.cloudfunctions.net/function-name'
        self.env = patch.dict('os.environ', {
            'GCS_BUCKET': 'unprocessed-rental-housing-data'
            })
        with open('sample_post_html.txt', 'r') as infile:
            self.sample_post_html = infile.read()

        self.test_request_json = {
            'href': 'https://some-url.com',
            'data_id': 123456756,
            'posted_at': '2020-01-01 14:00',
            'repost_of': None
        }

        self.test_request_json_with_repost = {
            'href': 'https://some-url.com',
            'data_id': 123456756,
            'posted_at': '2020-01-01 14:00',
            'repost_of': 748593828
        }

    @responses.activate
    def test_handler_accepts_post_request(self):
        """
        Test the request handler accepts POST requests and returns (data, 201)

        """
        with self.env:
            responses.add(method=responses.GET, url=self.test_request_json['href'], status=200, body=self.sample_post_html)
            responses.add(method=responses.POST, url='https://oauth2.googleapis.com/token', status=200)
            request = Mock(get_json=Mock(return_value=self.test_request_json), method='POST', args=self.test_request_json)
            self.assertEqual(main.handler(request), (self.test_request_json, 201))

    def test_handler_returns_405_on_other_request_types(self):
        """
        Test the request handler returns (message, 405) on any other request types
        """
        request = Mock(get_json=Mock(return_value=self.test_request_json), method='GET', args=self.test_request_json)
        self.assertEqual(main.handler(request), ({'message': 'Only POST requests permitted.'}, 405))

    def test_handler_returns_400_on_missing_data(self):
        """
        Test the request handler returns (message, 400) on missing `href`
        """
        self.test_data_no_href = self.test_request_json.pop('href')
        request = Mock(get_json=Mock(return_value=self.test_data_no_href), method='POST', args=self.test_data_no_href)
        self.assertEqual(main.handler(request), ({'message': 'Missing required `href` in request.'}, 400))

    @responses.activate
    def test_get_html(self):
        """
        Test the function performs the GET request and returns html text
        """
        url_to_get = 'https://www.some-url-to-get.com'
        responses.add(method=responses.GET, url=url_to_get, status=200, body=self.sample_post_html)
        self.assertEqual(main.get_html(url_to_get), self.sample_post_html)

    # # TODO: currently test failing with `AssertionError: ConnectionError not raised`
    @responses.activate
    @patch('google.cloud.error_reporting')
    def test_get_html_raises_connection_error(self):
        """
        Test the function raises ConnectionError
        """
        url_to_get = 'https://www.some-invalid-url-which-returns-error-status-code.com'
        responses.add(method=responses.GET, url=url_to_get)
        responses.add(method=responses.POST, url='https://oauth2.googleapis.com/token', status=200)
        with self.assertRaises(requests.exceptions.ConnectionError):
            main.get_html(url_to_get)

    # # TODO: currently test failing with google.cloud error reporting exception
    # #       `google.api_core.exceptions.ServiceUnavailable: 503 Getting metadata from plugin failed with error:
    # #        Expecting value: line 1 column 1 (char 0)`
    @responses.activate
    def test_get_html_raises_http_error_on_4xx_error_status_code(self):
        """
        Test the function raises HTTPError on responses where the status code != 200
        """
        url_to_get = 'https://www.some-invalid-url-which-returns-error-status-code.com'
        oauth_endpoint = 'https://oauth2.googleapis.com/token'
        responses.add(method=responses.GET, url=url_to_get, status=400, body='')
        responses.add(method=responses.POST, url=oauth_endpoint, status=200)
        with self.assertRaises(requests.exceptions.HTTPError):
            main.get_html(url_to_get)

    def test_get_headers(self):
        """
        Test the function returns headers with the same keys
        """
        url = 'https://vancouver.craigslist.org/rds/apa/d/surrey-house-is-located-in-guildford/7126587889.html'
        headers = main.get_headers(url)
        self.assertEqual(headers.keys(), main.HEADERS.keys())

    def test_get_headers_is_modified(self):
        """
        Test the function returns headers (Host, Referer, User-Agent) that have been modified
        """
        url = 'https://vancouver.craigslist.org/rds/apa/d/surrey-house-is-located-in-guildford/7126587889.html'
        headers = main.get_headers(url)
        self.assertNotEqual(headers['Host'], main.HEADERS['Host'])
        self.assertNotEqual(headers['Referer'], main.HEADERS['Referer'])
        self.assertNotEqual(headers['User-Agent'], main.HEADERS['User-Agent'])

    # TODO: Complete this test
    @patch('google.cloud.storage.Client')
    def test_upload_to_google_cloud_storage(self):
        """
        Test the function returns true when a string is uploaded to Google Cloud Storage as a new object
        or returns false on failure
        """
        pass