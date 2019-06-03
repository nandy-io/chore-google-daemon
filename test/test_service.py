import unittest
import unittest.mock

import os
import copy
import yaml
import datetime

import service

class MockRedis:

    def __init__(self, host, port):

        self.host = host
        self.port = port

        self.data = {}
        self.expires = {}

    def get(self, key):

        if key in self.data:
            return self.data[key]

        return None

    def set(self, key, value, ex=None):

        self.data[key] = value
        self.expires[key] = ex


class TestService(unittest.TestCase):

    @unittest.mock.patch.dict(os.environ, {
        "CHORE_API": "http://toast.com",
        "GOOGLE_CALENDAR": "peeps",
        "REDIS_HOST": "most.com",
        "REDIS_PORT": "667",
        "REDIS_PREFIX": "stuff",
        "RANGE": "10",
        "SLEEP": "7"
    })
    @unittest.mock.patch("redis.StrictRedis", MockRedis)
    @unittest.mock.patch("googleapiclient.discovery.build", unittest.mock.MagicMock())
    @unittest.mock.patch("oauth2client.file.Storage", unittest.mock.MagicMock())
    @unittest.mock.patch("httplib2.Http", unittest.mock.MagicMock())
    @unittest.mock.patch("builtins.open", create=True)
    def setUp(self, mock_open):

        mock_open.side_effect = [
            unittest.mock.mock_open(read_data='{"name": "peeps"}').return_value
        ]

        self.daemon = service.Daemon()

    @unittest.mock.patch.dict(os.environ, {
        "CHORE_API": "http://toast.com",
        "GOOGLE_CALENDAR": "peeps",
        "REDIS_HOST": "most.com",
        "REDIS_PORT": "667",
        "REDIS_PREFIX": "stuff",
        "RANGE": "10",
        "SLEEP": "7"
    })
    @unittest.mock.patch("redis.StrictRedis", MockRedis)
    @unittest.mock.patch("googleapiclient.discovery.build")
    @unittest.mock.patch("oauth2client.file.Storage")
    @unittest.mock.patch("httplib2.Http")
    @unittest.mock.patch("builtins.open", create=True)
    def test___init__(self, mock_open, mock_http, mock_storage, mock_build):

        mock_open.side_effect = [
            unittest.mock.mock_open(read_data='{"name": "people"}').return_value
        ]

        mock_api = unittest.mock.MagicMock()
        mock_api.calendarList.return_value.list.return_value.execute.return_value.get.return_value = [
            {
                "summary": "people",
                "id": "peeps"
            },
            {
                "summary": "things",
                "id": "teeps"
            }
        ]
        mock_storage.return_value.get.return_value.authorize.return_value = "www"
        mock_http.return_value = "web"
        mock_build.return_value = mock_api

        daemon = service.Daemon()

        self.assertEqual(daemon.chore, "http://toast.com")
        self.assertEqual(daemon.calendar, "people")
        self.assertEqual(daemon.redis.host, "most.com")
        self.assertEqual(daemon.redis.port, 667)
        self.assertEqual(daemon.prefix, "stuff/event")
        self.assertEqual(daemon.range, 10)
        self.assertEqual(daemon.sleep, 7)
        self.assertEqual(daemon.calendar_id, "peeps")

        mock_open.assert_called_once_with('/opt/service/secret/calendar.json', 'r')
        mock_build.assert_called_once_with("calendar", "v3", http="www")
        mock_storage.assert_called_once_with('/opt/service/token.json')
        mock_storage.return_value.get.return_value.authorize.assert_called_once_with("web")
        mock_api.calendarList.return_value.list.return_value.execute.return_value.get.assert_called_once_with("items", [])

    @unittest.mock.patch("service.time.time", unittest.mock.MagicMock(return_value=7))
    def test_check(self):

        self.assertFalse(self.daemon.check({"id": "meow"}))
        self.assertEqual(self.daemon.cache, {"meow": 7})
        self.assertEqual(self.daemon.redis.data, {"stuff/event/meow": True})
        self.assertEqual(self.daemon.redis.expires, {"stuff/event/meow": 20})

        self.assertTrue(self.daemon.check({"id": "meow"}))

        self.daemon.cache = {}
        self.assertTrue(self.daemon.check({"id": "meow"}))

    @unittest.mock.patch("service.time.time", unittest.mock.MagicMock(return_value=7))
    def test_clear(self):

        self.daemon.range = 2
        self.daemon.cache = {
            "stay": 3,
            "go": 2
        }

        self.daemon.clear()

        self.assertEqual(self.daemon.cache, {"stay": 3})

    @unittest.mock.patch("requests.post")
    @unittest.mock.patch("requests.patch")
    def test_event(self, mock_patch, mock_post):

        self.daemon.cache["done"] = True

        self.daemon.event({
            "id": "nope",
            "description": "nope"
        })
        mock_post.assert_not_called()

        self.daemon.event({
            "id": "empty",
            "description": yaml.safe_dump({}, default_flow_style=False)
        })
        mock_post.assert_not_called()

        self.daemon.event({
            "id": "done",
            "description": yaml.safe_dump_all([
                {"routine": "done"}
            ])
        })
        mock_post.assert_not_called()

        self.daemon.event({
            "id": "do",
            "description": yaml.safe_dump_all([
                {"routine": "now"},
                {"todo": "it"},
                {"todos": "them"}
            ])
        })
        mock_post.assert_has_calls([
            unittest.mock.call("http://toast.com/routine", json={"routine": "now"}),
            unittest.mock.call().raise_for_status(),
            unittest.mock.call("http://toast.com/todo", json={"todo": "it"}),
            unittest.mock.call().raise_for_status()
        ])
        mock_patch.assert_has_calls([
            unittest.mock.call("http://toast.com/todo", json={"todos": "them"}),
            unittest.mock.call().raise_for_status()
        ])

    @unittest.mock.patch("service.datetime")
    @unittest.mock.patch("traceback.format_exc")
    @unittest.mock.patch('builtins.print')
    def test_process(self, mock_print, mock_traceback, mock_datetime):

        mock_datetime.timedelta = datetime.timedelta
        mock_datetime.timezone = datetime.timezone
        mock_datetime.datetime.utcnow.return_value = datetime.datetime(2018, 12, 13, 14, 15, 16, tzinfo=datetime.timezone.utc)

        self.daemon.calendar_id = "peeps"
        self.daemon.calendar_api = unittest.mock.MagicMock()

        self.daemon.cache["done"] = True

        self.daemon.calendar_api.events.return_value.list.return_value.execute.return_value.get.return_value = [
            {"description": "doh"}
        ]

        self.daemon.event = unittest.mock.MagicMock(side_effect=[Exception("whoops")])
        mock_traceback.return_value = "spirograph"

        self.daemon.process()

        self.daemon.calendar_api.events.return_value.list.assert_called_once_with(
            calendarId="peeps", 
            timeMin="2018-12-13T14:15:06+00:00Z", 
            timeMax="2018-12-13T14:15:16+00:00Z", 
            singleEvents=True
        )
        self.daemon.calendar_api.events.return_value.list.return_value.execute.return_value.get.assert_called_once_with("items", [])

        self.daemon.event.assert_called_once_with({"description": "doh"})

        mock_print.assert_has_calls([
            unittest.mock.call("whoops"),
            unittest.mock.call("spirograph")
        ])

    @unittest.mock.patch("requests.post")
    @unittest.mock.patch("service.datetime")
    @unittest.mock.patch("service.time.sleep")
    @unittest.mock.patch("service.time.time", unittest.mock.MagicMock(return_value=7))
    def test_run(self, mock_sleep, mock_datetime, mock_post):

        self.daemon.range = 2
        self.daemon.cache = {
            "go": 2
        }

        mock_datetime.timedelta = datetime.timedelta
        mock_datetime.timezone = datetime.timezone
        mock_datetime.datetime.utcnow.return_value = datetime.datetime(2018, 12, 13, 14, 15, 16, tzinfo=datetime.timezone.utc)

        self.daemon.calendar_id = "peeps"
        self.daemon.calendar_api = unittest.mock.MagicMock()

        self.daemon.calendar_api.events.return_value.list.return_value.execute.return_value.get.return_value = [
            {
                "id": "do",
                "description": yaml.safe_dump_all([
                    {"routine": "now"}
                ])
            }
        ]
        mock_sleep.side_effect = [Exception("doh")]

        self.assertRaisesRegex(Exception, "doh", self.daemon.run)

        mock_post.assert_has_calls([
            unittest.mock.call("http://toast.com/routine", json={"routine": "now"}),
            unittest.mock.call().raise_for_status()
        ])

        self.assertEqual(self.daemon.cache, {"do": 7})

        mock_sleep.assert_called_with(7)