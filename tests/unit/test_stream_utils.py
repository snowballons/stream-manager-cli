from src.streamwatch.stream_utils import parse_url_metadata


class TestUrlParsing:
    def test_parse_twitch_url(self):
        result = parse_url_metadata("https://www.twitch.tv/some_streamer")
        assert result["platform"] == "Twitch"
        assert result["username"] == "some_streamer"

    def test_parse_youtube_url(self):
        result = parse_url_metadata("https://www.youtube.com/@testchannel")
        assert result["platform"] == "YouTube"
        assert result["username"] == "testchannel"
