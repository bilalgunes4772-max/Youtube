import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
import automation as app

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.state=Path(self.tmp.name)
        self.episodes=[{'id':'episode-1'},{'id':'episode-2'},{'id':'episode-3'}]
        self.config={'state_dir':str(self.state),'antalia_command':['verified-adapter']}
    def test_turkey_schedule_and_no_catchup(self):
        for hour in [12,19]:
            self.assertEqual(app.slot_now({},dt.datetime(2026,10,10,hour,0,tzinfo=ZoneInfo('Europe/Istanbul'))),f'2026-10-10T{hour}:00')
        with self.assertRaises(app.Blocked): app.slot_now({},dt.datetime(2026,10,10,15,0,tzinfo=ZoneInfo('Europe/Istanbul')))
    def test_uploaded_slot_is_not_reused(self):
        with app.database(self.state) as db:
            self.assertEqual(app.reserve(db,'2026-10-10T12:00',self.episodes)['id'],'episode-1')
            db.execute("UPDATE jobs SET status='uploaded',video_id='abc'");db.commit()
            self.assertIsNone(app.reserve(db,'2026-10-10T12:00',self.episodes))
            self.assertEqual(app.reserve(db,'2026-10-10T19:00',self.episodes)['id'],'episode-2')
    def test_two_uploads_per_day_limit(self):
        with app.database(self.state) as db:
            for time in ['12:00','19:00']:
                app.reserve(db,'2026-10-10T'+time,self.episodes)
                db.execute("UPDATE jobs SET status='uploaded'");db.commit()
            with self.assertRaises(app.Blocked): app.reserve(db,'2026-10-10T20:00',self.episodes)
    def test_crash_during_upload_blocks_new_uploads(self):
        with app.database(self.state) as db:
            app.reserve(db,'2026-10-10T12:00',self.episodes)
            db.execute("UPDATE jobs SET status='uploading'");db.commit()
            with self.assertRaises(app.Blocked): app.reserve(db,'2026-10-10T19:00',self.episodes)
    def test_timeout_marks_uncertain_and_stops_retry(self):
        with patch.object(app,'youtube',return_value=object()),patch.object(app,'check_channel'),patch.object(app,'render',return_value=Path('/tmp/fake.mp4')),patch.object(app,'upload',side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):app.publish(self.config,self.episodes,'2026-10-10T12:00')
        with app.database(self.state) as db:
            self.assertEqual(db.execute('SELECT status FROM jobs').fetchone()[0],'uncertain')
    def test_render_failure_does_not_start_upload(self):
        with patch.object(app,'youtube',return_value=object()),patch.object(app,'check_channel'),patch.object(app,'render',side_effect=app.Blocked('TTS failed')),patch.object(app,'upload') as upload:
            with self.assertRaises(app.Blocked):app.publish(self.config,self.episodes,'2026-10-10T12:00')
            upload.assert_not_called()
        with app.database(self.state) as db:self.assertEqual(db.execute('SELECT status FROM jobs').fetchone()[0],'failed')
    def test_wrong_channel_is_rejected(self):
        from unittest.mock import MagicMock
        client=MagicMock();client.channels().list().execute.return_value={'items':[{'id':'wrong','snippet':{'customUrl':'@another-channel'}}]}
        with self.assertRaises(app.Blocked):app.check_channel(client,{})
    def test_success_records_id_and_next_run_does_not_upload(self):
        with patch.object(app,'youtube',return_value=object()),patch.object(app,'check_channel'),patch.object(app,'render',return_value=Path('/tmp/fake.mp4')),patch.object(app,'upload',return_value='video123') as upload:
            app.publish(self.config,self.episodes,'2026-10-10T12:00')
            app.publish(self.config,self.episodes,'2026-10-10T12:00')
            self.assertEqual(upload.call_count,1)
        with app.database(self.state) as db:self.assertEqual(db.execute('SELECT status,video_id FROM jobs').fetchone(),('uploaded','video123'))
    def test_preview_cannot_be_published_without_antalia(self):
        with self.assertRaises(app.Blocked):app.publish({},self.episodes,'2026-10-10T12:00')
    def test_empty_queue_stops(self):
        with app.database(self.state) as db:
            with self.assertRaises(app.Blocked): app.reserve(db,'2026-10-10T12:00',[])
    def test_worker_lock_prevents_overlap(self):
        with app.locked(self.state):
            with self.assertRaises(app.Blocked):
                with app.locked(self.state):pass
    def test_remote_ledger_failure_prevents_upload(self):
        with patch.object(app,'youtube',return_value=object()),patch.object(app,'check_channel'),patch.object(app,'render',return_value=Path('/tmp/fake.mp4')),patch.object(app,'persist_state',side_effect=RuntimeError('Git push failed')),patch.object(app,'upload') as upload:
            with self.assertRaises(RuntimeError):app.publish(self.config,self.episodes,'2026-10-10T12:00')
            upload.assert_not_called()
        with app.database(self.state) as db:self.assertEqual(db.execute('SELECT status FROM jobs').fetchone()[0],'uploading')
    def test_failed_render_can_retry_next_day(self):
        with app.database(self.state) as db:
            app.reserve(db,'2026-10-10T12:00',self.episodes)
            db.execute("UPDATE jobs SET status='failed'");db.commit()
            self.assertEqual(app.reserve(db,'2026-10-11T12:00',self.episodes)['id'],'episode-1')
    def test_abandoned_render_is_retried_without_skipping_episode(self):
        with app.database(self.state) as db:
            app.reserve(db,'2026-10-10T12:00',self.episodes)
            self.assertEqual(app.reserve(db,'2026-10-11T12:00',self.episodes)['id'],'episode-1')
    def test_token_permissions(self):
        path=self.state/'token.json';app.secure_write(path,'test')
        self.assertEqual(path.stat().st_mode & 0o777,0o600)

if __name__=='__main__':unittest.main()
