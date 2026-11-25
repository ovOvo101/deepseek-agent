"""通过真实本机 HTTP 验证前后端协议，模拟外部 API。"""
import json
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import server
from test_agent import plan, response


class ServerTests(unittest.TestCase):
    def test_http_agent_flow_and_file_boundary(self):
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{http.server_port}'
        try:
            with urllib.request.urlopen(base) as page:
                self.assertIn('AI 英语外教', page.read().decode())
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(base + '/.local-key.json')
            self.assertEqual(error.exception.code, 404)
            replies = iter([plan(), response({'tool_calls': [{'id': 'x', 'type': 'function', 'function': {'name': 'optimize_discounts', 'arguments': '{}'}}]}), plan(), response({'content': '最低实付336元'}), plan(True)])
            def api(path, key, payload=None):
                return {'data': [{'id': 'mock'}]} if path == 'models' else next(replies)
            config = json.loads((Path(__file__).parent / 'shopping.example.json').read_text())
            body = json.dumps({'shopping': config, 'prompt': '求最优优惠', 'model': 'mock'}).encode()
            with patch.object(server, 'load_key', return_value='test-only'), patch.object(server, 'request', side_effect=api):
                req = urllib.request.Request(base + '/api/run', data=body, headers={'Content-Type': 'application/json', 'Origin': base})
                with urllib.request.urlopen(req) as output:
                    events = [json.loads(line) for line in output]
            self.assertEqual(events[-1]['type'], 'result')
            self.assertEqual(events[-1]['quote']['最低实付'], '336.00')
            self.assertTrue(any('optimize_discounts' in e.get('message', '') for e in events))
            self.assertNotIn('test-only', json.dumps(events))
            from test_tutor import action, LESSON
            def tutor_api(path, key, payload=None):
                return {'data': [{'id': 'mock'}]} if path == 'models' else action('teach_and_wait', LESSON)
            body = json.dumps({'goal': '咖啡店点单', 'level': 'A2', 'history': [], 'student': '', 'model': 'mock'}).encode()
            with patch.object(server, 'load_key', return_value='test-only'), patch.object(server, 'request', side_effect=tutor_api):
                req = urllib.request.Request(base + '/api/tutor', data=body, headers={'Content-Type': 'application/json', 'Origin': base})
                with urllib.request.urlopen(req) as output:
                    events = [json.loads(line) for line in output]
            self.assertEqual(events[-1]['status'], 'waiting_for_student')
            self.assertEqual(events[-1]['lesson']['question'], 'What would you like?')
            self.assertNotIn('test-only', json.dumps(events))

        finally:
            http.shutdown()
            http.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
