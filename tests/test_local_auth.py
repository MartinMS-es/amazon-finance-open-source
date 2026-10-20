import base64
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_auth import LocalAuth, check_password, password_record, totp
from local_security import Sessions, ticket
import tempfile
def workspace_temp(parent):
    return tempfile.TemporaryDirectory(prefix='afos-test-', dir=parent)


class AuthTests(unittest.TestCase):
    def test_rfc6238_sha1_vectors(self):
        seed = base64.b32encode(b'12345678901234567890').decode()
        for timestamp, expected in [(59,'94287082'),(1111111109,'07081804'),(1111111111,'14050471'),(1234567890,'89005924'),(2000000000,'69279037'),(20000000000,'65353130')]:
            self.assertEqual(totp(seed,timestamp//30,8),expected)

    def test_password_policy(self):
        for value in ('short','LongButNoNumbers!','alllowercase123!','NOLOWERCASE123!','NoSpecialChar123'):
            with self.assertRaises(ValueError):password_record(value)
        record=password_record('Test-Only!Password123')
        self.assertTrue(check_password('Test-Only!Password123',record))
        self.assertFalse(check_password('Test-Only!Password124',record))

    def test_setup_login_replay_lockout_restart_change_expiry(self):
        with workspace_temp(Path(__file__).resolve().parent) as temporary:
            clock=1800000000
            with patch('local_auth.time.time',side_effect=lambda:clock):
                sessions=Sessions(b'test-only-key')
                auth=LocalAuth(temporary,sessions)
                with self.assertRaises(ValueError):auth.begin('invalid')
                enroll=auth.begin(ticket(sessions.key))
                password='Test-Only!Password123'
                session=auth.setup({'enrollment':enroll['enrollment'],'password':password,'code':totp(enroll['secret'],clock//30)})
                self.assertTrue(sessions.valid('__Host-afos_session='+session))
                self.assertNotIn(password.encode(),auth.path.read_bytes())
                self.assertNotIn(enroll['secret'].encode(),auth.path.read_bytes())
                with self.assertRaises(ValueError):auth.begin(ticket(sessions.key))
                with self.assertRaises(ValueError):auth.login({'password':password,'code':totp(enroll['secret'],clock//30)})
                clock+=30
                auth.login({'password':password,'code':totp(enroll['secret'],clock//30)})
                # Five failures persist across server restart.
                for _ in range(5):
                    with self.assertRaises(ValueError):auth.login({'password':'incorrect','code':'000000'})
                auth=LocalAuth(temporary,sessions)
                clock+=30
                with self.assertRaises(ValueError):auth.login({'password':password,'code':totp(enroll['secret'],clock//30)})
                clock+=301
                with self.assertRaises(ValueError):auth.login({'password':password,'code':totp(enroll['secret'],clock//30)})
                clock+=1500
                auth.login({'password':password,'code':totp(enroll['secret'],clock//30)})
                clock+=30
                auth.change({'password':password,'code':totp(enroll['secret'],clock//30),'new_password':'Replacement!Password456'})
                self.assertFalse(sessions.valid('__Host-afos_session='+session))
                clock+=30
                with self.assertRaises(ValueError):auth.change({'password':'Replacement!Password456','code':totp(enroll['secret'],clock//30),'new_password':password})
                clock+=366*86400
                with self.assertRaises(ValueError):auth.login({'password':'Replacement!Password456','code':totp(enroll['secret'],clock//30)})

    def test_enrollment_expiry(self):
        with workspace_temp(Path(__file__).resolve().parent) as temporary:
            sessions=Sessions(b'test-only-key')
            auth=LocalAuth(temporary,sessions)
            enroll=auth.begin(ticket(sessions.key))
            with patch('local_auth.time.time',return_value=time.time()+601):
                with self.assertRaises(ValueError):auth.setup({'enrollment':enroll['enrollment'],'password':'Test-Only!Password123','code':'000000'})


if __name__=='__main__':unittest.main()
