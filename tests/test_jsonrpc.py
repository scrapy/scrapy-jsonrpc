import json
import unittest
from io import BytesIO
from mock import patch
from six.moves import urllib

from scrapy_jsonrpc.jsonrpc import jsonrpc_client_call, jsonrpc_server_call, \
    JsonRpcError, jsonrpc_errors
from scrapy_jsonrpc.serialize import ScrapyJSONDecoder
from scrapy.utils.python import to_bytes, to_unicode
from tests.test_serialize import CrawlerMock


def _umock(result=None, error=None):
    response = {}
    if result is not None:
        response.update(result=result)
    if error is not None:
        response.update(error=error)
    return BytesIO(to_bytes(json.dumps(response)))


class TestTarget(object):

    def call(self, *args, **kwargs):
        return list(args), kwargs

    def exception(self):
        raise Exception("testing-errors")


class JsonRpcUtilsTestCase(unittest.TestCase):

    def setUp(self):
        crawler = CrawlerMock([])
        self.json_decoder = ScrapyJSONDecoder(crawler=crawler)

    def test_jsonrpc_client_call_args_kwargs_raises(self):
        self.assertRaises(ValueError, jsonrpc_client_call, 'url', 'test', 'one', kw=123)

    def test_jsonrpc_client_call_request(self):
        sentcall = {}
        def _urlopen(url, data):
            sentcall['url'] = url
            sentcall['data'] = data
            return _umock(1)

        with patch.object(urllib.request, 'urlopen', _urlopen):
            jsonrpc_client_call('url', 'test', 'one', 2)
            req = json.loads(to_unicode(sentcall['data']))
            assert 'id' in req
            self.assertEqual(sentcall['url'], 'url')
            self.assertEqual(req['jsonrpc'], '2.0')
            self.assertEqual(req['method'], 'test')
            self.assertEqual(req['params'], ['one', 2])

    @patch.object(urllib.request, 'urlopen')
    def test_jsonrpc_client_call_response(self, urlopen_mock):
        urlopen_mock.return_value = _umock()
        # must return result or error
        self.assertRaises(ValueError, jsonrpc_client_call, 'url', 'test')
        urlopen_mock.return_value = _umock(result={'one': 1})
        self.assertEqual(jsonrpc_client_call('url', 'test'), {'one': 1})
        urlopen_mock.return_value = _umock(error={'code': 123,
                                                  'message': 'hello',
                                                  'data': 'some data'})

        raised = False
        try:
            jsonrpc_client_call('url', 'test')
        except JsonRpcError as e:
            raised = True
            self.assertEqual(e.code, 123)
            self.assertEqual(e.message, 'hello')
            self.assertEqual(e.data, 'some data')
            assert '123' in str(e)
            assert 'hello' in str(e)
        assert raised, "JsonRpcError not raised"

    def test_jsonrpc_server_call(self):
        t = TestTarget()
        r = jsonrpc_server_call(t, b'invalid json data', self.json_decoder)
        assert 'error' in r
        assert r['jsonrpc'] == '2.0'
        assert r['id'] is None
        self.assertEqual(r['error']['code'], jsonrpc_errors.PARSE_ERROR)
        assert 'Traceback' in r['error']['data']

        r = jsonrpc_server_call(t, b'{"test": "test"}', self.json_decoder)
        assert 'error' in r
        assert r['jsonrpc'] == '2.0'
        assert r['id'] is None
        self.assertEqual(r['error']['code'], jsonrpc_errors.INVALID_REQUEST)

        r = jsonrpc_server_call(t, b'{"method": "notfound", "id": 1}', self.json_decoder)
        assert 'error' in r
        assert r['jsonrpc'] == '2.0'
        assert r['id'] == 1
        self.assertEqual(r['error']['code'], jsonrpc_errors.METHOD_NOT_FOUND)

        r = jsonrpc_server_call(t, b'{"method": "exception", "id": 1}', self.json_decoder)
        assert 'error' in r
        assert r['jsonrpc'] == '2.0'
        assert r['id'] == 1
        self.assertEqual(r['error']['code'], jsonrpc_errors.INTERNAL_ERROR)
        assert 'testing-errors' in r['error']['message']
        assert 'Traceback' in r['error']['data']

        r = jsonrpc_server_call(t, b'{"method": "call", "id": 2}', self.json_decoder)
        assert 'result' in r
        assert r['jsonrpc'] == '2.0'
        assert r['id'] == 2
        self.assertEqual(r['result'], ([], {}))

        r = jsonrpc_server_call(t, b'{"method": "call", "params": [456, 123], "id": 3}',
                                self.json_decoder)
        assert 'result' in r
        assert r['jsonrpc'] == '2.0'
        assert r['id'] == 3
        self.assertEqual(r['result'], ([456, 123], {}))

        r = jsonrpc_server_call(t, b'{"method": "call", "params": {"data": 789}, "id": 3}',
                                self.json_decoder)
        assert 'result' in r
        assert r['jsonrpc'] == '2.0'
        assert r['id'] == 3
        self.assertEqual(r['result'], ([], {'data': 789}))
