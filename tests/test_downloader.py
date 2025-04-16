import os
import unittest
from src.downloader import download_track, copy_existing_track

class TestDownloader(unittest.TestCase):

    def setUp(self):
        self.track_id = "test_track_id"
        self.track_path = "test_track.mp3"
        self.source_folder = "source_folder"
        self.destination_folder = "destination_folder"
        os.makedirs(self.source_folder, exist_ok=True)
        os.makedirs(self.destination_folder, exist_ok=True)
        with open(os.path.join(self.source_folder, "test_track.mp3"), "w") as f:
            f.write("test content")

    def tearDown(self):
        if os.path.exists(self.track_path):
            os.remove(self.track_path)
        if os.path.exists(self.source_folder):
            shutil.rmtree(self.source_folder)
        if os.path.exists(self.destination_folder):
            shutil.rmtree(self.destination_folder)

    def test_download_track(self):
        download_track(self.track_id, self.track_path)
        self.assertTrue(os.path.exists(self.track_path))

    def test_copy_existing_track(self):
        copy_existing_track("test_track", self.source_folder, self.destination_folder)
        self.assertTrue(os.path.exists(os.path.join(self.destination_folder, "test_track.mp3")))

if __name__ == "__main__":
    unittest.main()
