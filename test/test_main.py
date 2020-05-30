from unittest import mock, TestCase
from templates import HEADERS
from google.cloud import storage, exceptions
import main
import requests
import time
import os


class TestCloudFunction(TestCase):
    def setUp(self):
        self.TEST_CLOUD_FN_ENDPOINT = 'https://cloud-function-location-project-name.cloudfunctions.net/function-name'
        self.TEST_URL_TO_GET = 'https://location.craigslist.org/subloc/apa/d/post-title/post-id.html'
        self.env = mock.patch.dict('os.environ', {
            'GCS_BUCKET': 'unprocessed-rental-housing-data'
            })
        with open('sample_post_html.txt', 'r') as infile:
            self.sample_post_html = infile.read()
        
        self.json_data_to_upload = {
            'href': 'https://some-url.com',
            'data_id': 1111111111,
            'posted_at': '2020-01-01 14:00',
            'repost_of': 1111111112,
            'html': self.sample_post_html
        }

        self.incoming_json_data = self.json_data_to_upload.copy()
        self.incoming_json_data.pop('html')

        self.blob_name = str(self.json_data_to_upload['data_id']) + '.txt'

    def test_get_headers(self):
        """
        Test the function returns headers (Host, Referer, User-Agent) that have been updated
        """
        headers = main.get_headers(self.TEST_URL_TO_GET)
        self.assertNotEqual(headers['Host'], HEADERS['Host'])
        self.assertNotEqual(headers['Referer'], HEADERS['Referer'])
        self.assertNotEqual(headers['User-Agent'], HEADERS['User-Agent'])

    @mock.patch('main.requests.get')
    @mock.patch('main.get_headers')
    def test_get_html(self, mock_get_headers, mock_get_request):
        """
        Test the function performs the GET request and returns html text
        """

        mock_get_headers.return_value = HEADERS

        mock_get_request.return_value.status_code = 200
        mock_get_request.return_value.text = self.sample_post_html

        html_str = main.get_html(self.TEST_URL_TO_GET)
        self.assertEqual(html_str, self.sample_post_html)

    @mock.patch('main.error_reporting.Client.report')
    @mock.patch('main.requests.get')
    @mock.patch('main.get_headers')
    def test_get_html_raises_exception_on_error_code(self, mock_get_headers, mock_get_request, mock_err_report):
        """
        Test the function performs the GET request which raises an exception on error codes (4xx/5xx).
        When the exception is raised, a report is sent
        """

        mock_get_headers.return_value = HEADERS

        mock_get_request.return_value.status_code = 400
        mock_get_request.side_effect = requests.exceptions.RequestException()
        mock_err_report.message = 'test error msg'

        self.assertEqual(main.get_html(self.TEST_URL_TO_GET), '')

    @mock.patch('main.storage.Client.upload_from_string')
    @mock.patch('main.storage.Client.blob')
    @mock.patch('main.storage.Client.get_bucket')
    @mock.patch('main.storage.Client')
    def test_upload_to_google_cloud_storage(self, mock_client, mock_get_bucket, mock_blob, mock_upload_from_string):
        """
        Test the function returns true when a string is uploaded to Google Cloud Storage as a new object
        or returns false on failure
        """

        # the function uses an env variable called `GCS_BUCKET`
        with self.env:

            mock_storage_client = mock_client()
            mock_get_bucket.return_value = storage.Bucket(mock_storage_client, name=os.environ['GCS_BUCKET'])

            mock_blob.return_value = storage.Blob(name=self.blob_name,
                                                  bucket=mock_get_bucket.return_value)

            mock_upload_from_string.return_value = None

            self.assertTrue(main.upload_to_google_cloud_storage(self.json_data_to_upload))

    @mock.patch('main.error_reporting.Client.report')
    @mock.patch('main.storage.Client.get_bucket')
    def test_upload_to_google_cloud_storage_handles_exceptions(self, mock_get_bucket, mock_err_report):
        """
        Test the function handles an exception thrown while uploading the object to Google Cloud Storage.
        """

        mock_get_bucket.side_effect = exceptions.NotFound(
            '404 GET https://storage.googleapis.com/storage/v1/b/some-bucket-name: Not Found')
        mock_err_report.message = 'test error msg'

        self.assertFalse(main.upload_to_google_cloud_storage(self.json_data_to_upload))

    @mock.patch('main.upload_to_google_cloud_storage')
    @mock.patch('main.get_html')
    @mock.patch('flask.Request')
    def test_handler(self, mock_request, mock_get_html, mock_upload_to_google_cloud_storage):
        """
        Test handler returns (data, 201) on success of two tasks:  1) capture html 2) object upload to cloud storage
        """

        mock_request.get_json.return_value = self.incoming_json_data
        mock_request.get_json.silent = True
        mock_request.method = 'POST'

        mock_get_html.return_value = self.sample_post_html

        mock_upload_to_google_cloud_storage.return_value = True

        self.assertEqual(main.handler(mock_request), (self.json_data_to_upload, 201))

    @mock.patch('flask.Request')
    def test_handler_returns_405_on_other_request_types(self, mock_request):
        """
        Test handler returns (data, 405) on requests where method is not POST
        """

        mock_request.get_json.return_value = self.incoming_json_data
        mock_request.get_json.silent = True
        mock_request.method = 'GET'

        self.assertEqual(main.handler(mock_request), ({'message': 'Only POST requests permitted.'}, 405))

    @mock.patch('flask.Request')
    def test_handler_returns_400_on_missing_data_href(self, mock_request):
        """
        Test handler returns (data, 400) on requests when `href` isn't present in data
        """

        incoming_json_data_with_missing_href = self.incoming_json_data.copy()
        incoming_json_data_with_missing_href.pop('href')

        mock_request.get_json.return_value =  incoming_json_data_with_missing_href
        mock_request.get_json.silent = True
        mock_request.method = 'POST'

        self.assertEqual(main.handler(mock_request), ({'message': 'Missing required `href` in request.'}, 400))

    @mock.patch('main.get_html')
    @mock.patch('flask.Request')
    def test_handler_returns_200_on_failed_get_request(self, mock_request, mock_get_html):
        """
        Test handler returns (data, 200) when GET request fails.

        """

        mock_request.get_json.return_value = self.incoming_json_data
        mock_request.get_json.silent = True
        mock_request.method = 'POST'

        mock_get_html.return_value = ''

        expected = self.incoming_json_data.copy()
        expected.update({'message': 'GET request failed. See error reporting console for details.'})

        self.assertEqual(main.handler(mock_request), (expected, 200))

    @mock.patch('main.upload_to_google_cloud_storage')
    @mock.patch('main.get_html')
    @mock.patch('flask.Request')
    def test_handler_returns_200_on_failed_upload_to_gcs(self, mock_request, mock_get_html, mock_upload_to_gcs):
        """
        Test handler returns (data, 200) when upload to Google Cloud Storage fails.

        """

        mock_request.get_json.return_value = self.incoming_json_data
        mock_request.get_json.silent = True
        mock_request.method = 'POST'

        mock_get_html.return_value = self.sample_post_html

        mock_upload_to_gcs.return_value = False

        expected = self.json_data_to_upload.copy()
        expected.update({'message': 'Upload to Google Cloud Storage failed. See error reporting console for details.'})

        self.assertEqual(main.handler(mock_request), (expected, 200))
