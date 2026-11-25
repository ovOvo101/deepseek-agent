"""通过真实本机 HTTP 验证前后端协议，模拟外部 API。"""
import json
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import server


class ServerTests(unittest.TestCase):
    def test_http_agent_flow_and_file_boundary(self):
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{http.server_port}'
        try:
            with urllib.request.urlopen(base) as page:
                self.assertIn('Story Atelier', page.read().decode())
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(base + '/.local-key.json')
            self.assertEqual(error.exception.code, 404)
            req = urllib.request.Request(base + '/api/run', data=b'{}')
            with self.assertRaises(urllib.error.HTTPError) as removed:
                urllib.request.urlopen(req)
            self.assertEqual(removed.exception.code, 404)
            event = threading.Event()
            server.ACTIVE['test-pause'] = event
            req = urllib.request.Request(base + '/api/stop', data=json.dumps({'request_id': 'test-pause'}).encode(), headers={'Content-Type': 'application/json', 'Origin': base})
            with urllib.request.urlopen(req) as output:
                self.assertTrue(json.load(output)['stopped'])
            self.assertTrue(event.is_set())
            server.ACTIVE.pop('test-pause')
            from test_tutor import action, LESSON
            def tutor_api(path, key, payload=None):
                return {'data': [{'id': 'mock'}]} if path == 'models' else action('teach_and_wait', LESSON)
            body = json.dumps({'goal': '咖啡店点单', 'history': [], 'student': '', 'model': 'mock'}).encode()
            with patch.object(server, 'load_key', return_value='test-only'), patch.object(server, 'request', side_effect=tutor_api):
                req = urllib.request.Request(base + '/api/tutor', data=body, headers={'Content-Type': 'application/json', 'Origin': base})
                with urllib.request.urlopen(req) as output:
                    events = [json.loads(line) for line in output]
            self.assertEqual(events[-1]['status'], 'waiting_for_student')
            self.assertEqual(events[-1]['lesson']['question'], 'What would you like?')
            self.assertNotIn('test-only', json.dumps(events))

            live = {'title': '睡眠', 'story': 'Good sleep helps.', 'evidence': ['sleep well'], 'reusable_phrases': [], 'missing_details': ['时间'], 'practice_matches': []}
            body = json.dumps({'goal': '聊日常', 'history': [], 'student': 'sleep well', 'model': 'mock'}).encode()
            for failure in (False, True):
                outputs = [{'lesson': LESSON, 'feedback': None, 'status': 'waiting_for_student'}, RuntimeError('模拟整理失败') if failure else {'card': live}]
                with patch.object(server, 'load_key', return_value='test-only'), patch.object(server, 'request', return_value={'data': [{'id': 'mock'}]}), patch.object(server, 'teach', side_effect=outputs) as teaching:
                    req = urllib.request.Request(base + '/api/tutor', data=body, headers={'Content-Type': 'application/json', 'Origin': base})
                    with urllib.request.urlopen(req) as output:
                        events = [json.loads(line) for line in output]
                self.assertEqual(events[-1]['type'], 'result')
                self.assertEqual(teaching.call_args.kwargs['mode'], 'card')
                self.assertEqual(teaching.call_args.args[1][-1]['content'], 'sleep well')
                if failure:
                    self.assertIn('material_warning', events[-1])
                else:
                    self.assertEqual(events[-1]['live_card']['title'], '睡眠')

        finally:
            http.shutdown()
            http.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
